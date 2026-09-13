from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE = Path(__file__).resolve().parent
DATA_PATH = BASE / "data" / "renewable_training_data.csv"
ARTIFACT_DIR = BASE / "saved_model"
ARTIFACT_DIR.mkdir(exist_ok=True)

LAGS = [1, 2, 3, 24, 48, 72]
ROLL_WINDOWS = [24, 72]
MAX_HORIZON = 72
FEATURE_COLS = (
    [f"gen_lag_{l}" for l in LAGS]
    + [f"gen_rollmean_{w}" for w in ROLL_WINDOWS]
    + [f"gen_rollstd_{w}" for w in ROLL_WINDOWS]
    + ["irr_origin", "ambient_origin", "module_origin", "plant_peak_reference_kw",
       "horizon", "target_hour_sin", "target_hour_cos", "target_doy_sin",
       "target_doy_cos", "target_dow", "irradiation_clim",
       "ambient_temperature_c_clim", "module_temperature_c_clim"]
)


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp_hour"], dtype={"plant_id": str})
    df = df.sort_values(["plant_id", "timestamp_hour"]).drop_duplicates(["plant_id", "timestamp_hour"])
    for col in ["generation_ac_kw", "ambient_temperature_c", "module_temperature_c", "irradiation", "plant_peak_reference_kw"]:
        df[col] = pd.to_numeric(df[col], errors="raise")
    df["generation_ac_kw"] = df["generation_ac_kw"].clip(lower=0)
    df["irradiation"] = df["irradiation"].clip(lower=0)
    return df.reset_index(drop=True)


def add_origin_features(df: pd.DataFrame) -> pd.DataFrame:
    blocks=[]
    for pid,g in df.groupby("plant_id", sort=False):
        g=g.sort_values("timestamp_hour").copy()
        for lag in LAGS:
            g[f"gen_lag_{lag}"]=g["generation_ac_kw"].shift(lag)
        shifted=g["generation_ac_kw"].shift(1)
        for w in ROLL_WINDOWS:
            g[f"gen_rollmean_{w}"]=shifted.rolling(w).mean()
            g[f"gen_rollstd_{w}"]=shifted.rolling(w).std()
        g["irr_origin"]=g["irradiation"]
        g["ambient_origin"]=g["ambient_temperature_c"]
        g["module_origin"]=g["module_temperature_c"]
        blocks.append(g)
    return pd.concat(blocks, ignore_index=True).sort_values(["plant_id","timestamp_hour"]).reset_index(drop=True)


def build_climatology(df: pd.DataFrame) -> pd.DataFrame:
    t=df.copy(); t["hour"]=t["timestamp_hour"].dt.hour
    return (t.groupby(["plant_id","hour"],as_index=False)[["irradiation","ambient_temperature_c","module_temperature_c"]]
              .mean().rename(columns={"irradiation":"irradiation_clim","ambient_temperature_c":"ambient_temperature_c_clim","module_temperature_c":"module_temperature_c_clim"}))


def make_panel(df: pd.DataFrame, clim: pd.DataFrame) -> pd.DataFrame:
    origin_cols=([f"gen_lag_{l}" for l in LAGS]+[f"gen_rollmean_{w}" for w in ROLL_WINDOWS]+[f"gen_rollstd_{w}" for w in ROLL_WINDOWS]+["irr_origin","ambient_origin","module_origin","plant_peak_reference_kw"])
    chunks=[]
    for pid,g in df.groupby("plant_id", sort=False):
        g=g.sort_values("timestamp_hour").reset_index(drop=True)
        valid=g.index[g[origin_cols].notna().all(axis=1)]
        records=[]
        for i in valid:
            max_h=min(MAX_HORIZON,len(g)-1-i)
            if max_h<1: continue
            base={c:g.at[i,c] for c in origin_cols}
            for h in range(1,max_h+1):
                j=i+h
                records.append({"plant_id":pid,"origin_time":g.at[i,"timestamp_hour"],"target_time":g.at[j,"timestamp_hour"],"horizon":h,"target":g.at[j,"generation_ac_kw"],**base})
        if records: chunks.append(pd.DataFrame(records))
    panel=pd.concat(chunks,ignore_index=True)
    panel["origin_time"]=pd.to_datetime(panel["origin_time"]); panel["target_time"]=pd.to_datetime(panel["target_time"])
    hr=panel["target_time"].dt.hour; doy=panel["target_time"].dt.dayofyear
    panel["target_hour_sin"]=np.sin(2*np.pi*hr/24); panel["target_hour_cos"]=np.cos(2*np.pi*hr/24)
    panel["target_doy_sin"]=np.sin(2*np.pi*doy/365.25); panel["target_doy_cos"]=np.cos(2*np.pi*doy/365.25)
    panel["target_dow"]=panel["target_time"].dt.dayofweek; panel["target_hour"]=hr
    panel=panel.merge(clim,left_on=["plant_id","target_hour"],right_on=["plant_id","hour"],how="left").drop(columns=["target_hour","hour"])
    return panel.dropna(subset=FEATURE_COLS+["target"]).reset_index(drop=True)


def fit_model(panel: pd.DataFrame, n_estimators: int) -> xgb.XGBRegressor:
    if len(panel) > 30000:
        panel = panel.sample(n=30000, random_state=42)
    X=panel[FEATURE_COLS].to_numpy(dtype=np.float32); y=panel["target"].to_numpy(dtype=np.float32)
    model=xgb.XGBRegressor(n_estimators=n_estimators,max_depth=3,learning_rate=.10,subsample=.85,colsample_bytree=.85,reg_lambda=1.0,objective="reg:squarederror",random_state=42,n_jobs=4,tree_method="hist")
    model.fit(X,y,verbose=False)
    return model


def metric(y,p):
    return {"mae_kw":float(mean_absolute_error(y,p)),"rmse_kw":float(mean_squared_error(y,p)**.5),"r2":float(r2_score(y,p))}


def bucket(h):
    return "1-24h" if h<=24 else ("25-48h" if h<=48 else "49-72h")


def interval_margins(val: pd.DataFrame, pred: np.ndarray, coverage=.80):
    abs_err=np.abs(val["target"].to_numpy()-pred)
    out={}
    for b in ["1-24h","25-48h","49-72h"]:
        m=val["horizon"].map(bucket).eq(b).to_numpy()
        out[b]=float(np.quantile(abs_err[m],coverage)) if m.any() else 0.0
    return out


def main():
    df=load_data(); feat=add_origin_features(df)
    stamps=np.array(sorted(df["timestamp_hour"].unique())); n=len(stamps)
    train_end=pd.Timestamp(stamps[int(n*.70)-1]); val_end=pd.Timestamp(stamps[int(n*.85)-1])
    clim_train=build_climatology(feat[feat["timestamp_hour"]<=train_end])
    panel=make_panel(feat,clim_train)
    tr=panel[panel["target_time"]<=train_end].copy(); va=panel[(panel["target_time"]>train_end)&(panel["target_time"]<=val_end)].copy(); te=panel[panel["target_time"]>val_end].copy()
    print(f"Rows={len(df):,} plants={df.plant_id.nunique()} timestamps={n}")
    print(f"Chronological split: train <= {train_end}; validation <= {val_end}; held-out test > {val_end}")
    print(f"Panel rows train={len(tr):,} val={len(va):,} test={len(te):,}",flush=True)
    eval_model=fit_model(tr,45)
    va_pred=np.clip(eval_model.predict(va[FEATURE_COLS].to_numpy(dtype=np.float32)),0,None)
    margins=interval_margins(va,va_pred)
    te_pred=np.clip(eval_model.predict(te[FEATURE_COLS].to_numpy(dtype=np.float32)),0,None)
    y=te["target"].to_numpy(); overall=metric(y,te_pred)
    half=np.array([margins[bucket(int(h))] for h in te["horizon"]]); p10=np.clip(te_pred-half,0,None); p90=te_pred+half
    coverage=float(((y>=p10)&(y<=p90)).mean())
    base_keys=te[["plant_id","target_time"]].copy()
    base_keys["timestamp_hour"]=base_keys["target_time"]-pd.Timedelta(hours=24)
    hist_base=df[["plant_id","timestamp_hour","generation_ac_kw"]].rename(columns={"generation_ac_kw":"persistence"})
    merged_base=base_keys.merge(hist_base,on=["plant_id","timestamp_hour"],how="left")
    pers=merged_base["persistence"].fillna(0.0).to_numpy(dtype=float)
    baseline=metric(y,pers)
    print("Evaluation model done. Saving the chronologically trained model as the deployment artifact...",flush=True)
    eval_model.save_model(ARTIFACT_DIR/"expected_generation_model.json")
    hist_cols=["plant_id","plant_label","timestamp_hour","generation_ac_kw","ambient_temperature_c","module_temperature_c","irradiation","plant_peak_reference_kw"]
    df[hist_cols].to_csv(ARTIFACT_DIR/"historical_generation.csv",index=False); clim_train.to_csv(ARTIFACT_DIR/"hourly_weather_patterns.csv",index=False)
    originals=df[~df["plant_label"].str.contains("_SYN",na=False)][["plant_id","plant_label","plant_peak_reference_kw"]].drop_duplicates()
    meta={"artifact_format":"xgboost_native_json_v2","xgboost_version":xgb.__version__,"dataset_file":DATA_PATH.name,"dataset_rows":int(len(df)),"training_plant_count":int(df.plant_id.nunique()),"training_plants":df[["plant_id","plant_label"]].drop_duplicates().to_dict("records"),"runtime_plants":originals.to_dict("records"),"first_timestamp":df.timestamp_hour.min().isoformat(),"trained_through":df.timestamp_hour.max().isoformat(),"chronological_split":{"train_fraction":.70,"validation_fraction":.15,"test_fraction":.15,"train_end":train_end.isoformat(),"validation_end":val_end.isoformat()},"feature_cols":FEATURE_COLS,"lags":LAGS,"roll_windows":ROLL_WINDOWS,"max_horizon_hours":72,"interval_half_width_kw":margins,"test_metrics":overall,"persistence_baseline_test_metrics":baseline,"test_interval_coverage":coverage,"training_note":"Model trained on the two original plants plus ten synthetic augmented variants (9,792 source rows). Training panel rows are chronologically restricted and capped to a reproducible 30,000-row sample for fast training. Held-out evaluation is split by target timestamp chronologically, not randomly.","runtime_note":"Only original Plant_1 and Plant_2 are exposed in the runtime dashboard.","weather_note":"Future target weather uses plant/hour climatology because no live future-weather forecast API is included."}
    (ARTIFACT_DIR/"forecast_model_settings.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    out=te[["plant_id","origin_time","target_time","horizon","target"]].copy(); out["p50_kw"]=te_pred; out["p10_kw"]=p10; out["p90_kw"]=p90; out["persistence_24h_kw"]=pers; out.to_csv(ARTIFACT_DIR/"test_forecast_results.csv",index=False)
    pd.DataFrame([{"model":"expected_generation_model",**overall,"interval_coverage":coverage},{"model":"previous_day_baseline",**baseline,"interval_coverage":np.nan}]).to_csv(ARTIFACT_DIR/"forecast_accuracy_metrics.csv",index=False)
    print("TEST",json.dumps(overall)); print("Coverage",coverage); print("Baseline",json.dumps(baseline)); print("Artifacts",ARTIFACT_DIR)
if __name__=="__main__": main()

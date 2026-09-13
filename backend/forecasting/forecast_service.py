from __future__ import annotations
from functools import lru_cache
import json
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb

BASE=Path(__file__).resolve().parent; ART=BASE/'saved_model'
def _bucket(h:int)->str: return '1-24h' if h<=24 else ('25-48h' if h<=48 else '49-72h')

@lru_cache(maxsize=1)
def load_artifacts():
    mp=ART/'forecast_model_settings.json'
    if not mp.exists(): raise FileNotFoundError('Forecast model files are missing. Run: python -m forecasting.train_forecast_model')
    meta=json.loads(mp.read_text(encoding='utf-8'))
    model=xgb.XGBRegressor(); model.load_model(ART/'expected_generation_model.json')
    history=pd.read_csv(ART/'historical_generation.csv',parse_dates=['timestamp_hour'],dtype={'plant_id':str})
    clim=pd.read_csv(ART/'hourly_weather_patterns.csv',dtype={'plant_id':str})
    return {'metadata':meta,'model':model,'history':history,'clim':clim}

def forecast_uncertainty_pct(p10,p90,cap): return round(max(0.,(float(p90)-float(p10))/2)/float(cap)*100,2) if cap>0 else 0.

def _origin_features(history,pid,origin,lags,windows):
    g=history[(history.plant_id==pid)&(history.timestamp_hour<=origin)].sort_values('timestamp_hour')
    need=max(lags+windows)+1
    if len(g)<need: raise ValueError(f'Not enough history for plant {pid}; need at least {need} rows')
    gen=g.generation_ac_kw.to_numpy(float); last=g.iloc[-1]; f={f'gen_lag_{l}':float(gen[-l]) for l in lags}
    for w in windows:
        vals=gen[-w:]; f[f'gen_rollmean_{w}']=float(vals.mean()); f[f'gen_rollstd_{w}']=float(vals.std(ddof=1))
    f.update(irr_origin=float(last.irradiation),ambient_origin=float(last.ambient_temperature_c),module_origin=float(last.module_temperature_c),plant_peak_reference_kw=float(last.plant_peak_reference_kw))
    return f

def forecast_for_plant(plant_id:int|str,horizon_hours:int=72,origin_time=None):
    if not 1<=horizon_hours<=72: raise ValueError('horizon_hours must be between 1 and 72')
    a=load_artifacts(); meta=a['metadata']; model=a['model']; history=a['history']; clim=a['clim']; pid=str(plant_id)
    allowed={str(x['plant_id']) for x in meta['runtime_plants']}
    if pid not in allowed: raise ValueError(f'Unknown runtime plant_id={plant_id}. Available: {sorted(allowed)}')
    hp=history[history.plant_id==pid].sort_values('timestamp_hour')
    requested_origin=hp.timestamp_hour.max() if origin_time is None else pd.Timestamp(origin_time)
    latest_history=hp.timestamp_hour.max()
    # Historical dates use history up to that selected time. Upcoming dates use the latest
    # measured plant state as context while calendar/hour patterns come from the selected date.
    history_origin=min(requested_origin, latest_history)
    base=_origin_features(history,pid,history_origin,[int(x) for x in meta['lags']],[int(x) for x in meta['roll_windows']])
    origin=requested_origin
    cp=clim[clim.plant_id==pid].set_index('hour'); cap=float(base['plant_peak_reference_kw']); rows=[]; times=[]
    for h in range(1,horizon_hours+1):
        t=origin+pd.Timedelta(hours=h); c=cp.loc[t.hour]; r=dict(base); r.update(horizon=h,target_hour_sin=float(np.sin(2*np.pi*t.hour/24)),target_hour_cos=float(np.cos(2*np.pi*t.hour/24)),target_doy_sin=float(np.sin(2*np.pi*t.dayofyear/365.25)),target_doy_cos=float(np.cos(2*np.pi*t.dayofyear/365.25)),target_dow=int(t.dayofweek),irradiation_clim=float(c.irradiation_clim),ambient_temperature_c_clim=float(c.ambient_temperature_c_clim),module_temperature_c_clim=float(c.module_temperature_c_clim)); rows.append(r); times.append(t)
    X=pd.DataFrame(rows)[meta['feature_cols']].to_numpy(dtype=np.float32); p50=np.clip(model.predict(X),0,None); target_hours=np.array([t.hour for t in times]); night_mask=(target_hours < 6) | (target_hours >= 19); p50[night_mask]=0.0; widths=meta['interval_half_width_kw']; points=[]
    for i,h in enumerate(range(1,horizon_hours+1)):
        half=float(widths.get(_bucket(h),0.)); p10=max(0.,float(p50[i])-half); p90=float(p50[i])+half;
        if night_mask[i]: p10=0.0; p90=0.0
        cf=float(p50[i])/cap if cap else 0.0
        if night_mask[i]: flag='night/low-sun'
        elif cf >= 0.75: flag='expected high generation'
        elif cf <= 0.15: flag='expected low generation'
        else: flag='within normal range'
        points.append({'plant_id':int(pid) if pid.isdigit() else pid,'origin_time':origin.isoformat(),'history_reference_time':history_origin.isoformat(),'target_time':times[i].isoformat(),'horizon':h,'p10_kw':round(p10,3),'p50_kw':round(float(p50[i]),3),'p90_kw':round(p90,3),'expected_capacity_factor':round(cf,4),'forecast_uncertainty_pct':forecast_uncertainty_pct(p10,p90,cap),'flag':flag})
    return {'plant_id':int(pid) if pid.isdigit() else pid,'plant_reference_capacity_kw':cap,'trained_through':meta['trained_through'],'backend':f"xgboost-native-json ({meta.get('xgboost_version','unknown')})",'horizon_hours':horizon_hours,'points':points,'uncertainty_method':'Expected generation with a calibrated lower-to-upper likely range.','weather_note':meta['weather_note'],'training_note':meta['training_note']}


def _feature_frame_for_plant(plant_id: int | str, horizon: int = 1, origin_time=None):
    """Build the exact single-row feature frame used by the deployed forecast model."""
    if not 1 <= int(horizon) <= 72:
        raise ValueError("horizon must be between 1 and 72")
    a = load_artifacts(); meta=a['metadata']; history=a['history']; clim=a['clim']; pid=str(plant_id)
    allowed={str(x['plant_id']) for x in meta['runtime_plants']}
    if pid not in allowed:
        raise ValueError(f"Unknown runtime plant_id={plant_id}. Available: {sorted(allowed)}")
    hp=history[history.plant_id==pid].sort_values('timestamp_hour')
    origin=hp.timestamp_hour.max() if origin_time is None else pd.Timestamp(origin_time)
    history_origin=min(origin, hp.timestamp_hour.max())
    base=_origin_features(history,pid,history_origin,[int(x) for x in meta['lags']],[int(x) for x in meta['roll_windows']])
    t=origin+pd.Timedelta(hours=int(horizon)); cp=clim[clim.plant_id==pid].set_index('hour'); c=cp.loc[t.hour]
    r=dict(base); r.update(horizon=int(horizon),target_hour_sin=float(np.sin(2*np.pi*t.hour/24)),target_hour_cos=float(np.cos(2*np.pi*t.hour/24)),target_doy_sin=float(np.sin(2*np.pi*t.dayofyear/365.25)),target_doy_cos=float(np.cos(2*np.pi*t.dayofyear/365.25)),target_dow=int(t.dayofweek),irradiation_clim=float(c.irradiation_clim),ambient_temperature_c_clim=float(c.ambient_temperature_c_clim),module_temperature_c_clim=float(c.module_temperature_c_clim))
    return pd.DataFrame([r])[meta['feature_cols']], origin, t


def explain_forecast_for_plant(plant_id: int | str, horizon: int = 1, top_n: int = 8, origin_time=None) -> dict:
    """Explain one expected-generation forecast."""
    import shap
    a=load_artifacts(); model=a['model']; meta=a['metadata']
    X, origin, target = _feature_frame_for_plant(plant_id, horizon, origin_time=origin_time)
    explainer=shap.TreeExplainer(model)
    values=np.asarray(explainer.shap_values(X.to_numpy(dtype=np.float32)))
    if values.ndim==2: values=values[0]
    items=[]
    for feature,value,impact in zip(meta['feature_cols'],X.iloc[0].to_numpy(dtype=float),values):
        impact=float(impact)
        items.append({'feature':str(feature),'value':float(value),'shap_value_kw':impact,'direction':'increases forecast' if impact>0 else ('decreases forecast' if impact<0 else 'neutral')})
    items.sort(key=lambda x:abs(x['shap_value_kw']),reverse=True)
    pred=forecast_for_plant(plant_id,horizon_hours=int(horizon),origin_time=origin)['points'][int(horizon)-1]
    return {'plant_id':pred['plant_id'],'origin_time':origin.isoformat(),'target_time':target.isoformat(),'horizon':int(horizon),'p50_kw':pred['p50_kw'],'base_value_kw':float(np.asarray(explainer.expected_value).reshape(-1)[0]),'top_features':items[:max(1,min(int(top_n),len(items)))],'method':'Feature contribution explanation for the selected expected-generation forecast.'}



def forecast_origin_bounds(plant_id: int | str) -> dict:
    """Return safe selectable origin times for the 72-hour forecast UI."""
    a = load_artifacts(); meta = a['metadata']; history = a['history']; pid = str(plant_id)
    allowed = {str(x['plant_id']) for x in meta['runtime_plants']}
    if pid not in allowed:
        raise ValueError(f'Unknown runtime plant_id={plant_id}. Available: {sorted(allowed)}')
    hp = history[history.plant_id == pid].sort_values('timestamp_hour')
    if hp.empty:
        raise ValueError(f'No forecast history found for plant {plant_id}')
    required_history_hours = max([int(x) for x in meta['lags']] + [int(x) for x in meta['roll_windows']])
    earliest = hp.timestamp_hour.min() + pd.Timedelta(hours=required_history_hours)
    latest_history = hp.timestamp_hour.max()
    # Allow upcoming planning dates. The model still uses the latest measured plant state
    # as context when the selected start time is after the recorded history.
    now_hour = pd.Timestamp.now().floor('h')
    latest_selectable = max(latest_history, now_hour + pd.Timedelta(days=30))
    return {
        'earliest_origin_time': earliest.isoformat(),
        'latest_origin_time': latest_selectable.isoformat(),
        'latest_historical_origin_time': latest_history.isoformat(),
        'future_planning_days': 30,
    }

def forecast_model_metrics() -> dict:
    a=load_artifacts(); m=a['metadata']
    return {'dataset_rows':m['dataset_rows'],'training_plant_count':m['training_plant_count'],'chronological_split':m['chronological_split'],'test_metrics':m['test_metrics'],'persistence_baseline_test_metrics':m['persistence_baseline_test_metrics'],'test_interval_coverage':m['test_interval_coverage'],'training_note':m['training_note'],'runtime_note':m['runtime_note']}

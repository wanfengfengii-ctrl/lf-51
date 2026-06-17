import math
import copy
from typing import List, Dict, Tuple, Optional, Any

GRAVITY = 9.81


def get_cross_sectional_area(shape: str, water_level: float, capacity: float, shape_params: Optional[str] = None) -> float:
    if shape == 'cylindrical':
        return capacity / max(capacity, 1e-6) * math.pi * 1.0
    elif shape == 'conical':
        ratio = water_level / capacity if capacity > 0 else 0
        return (ratio ** 2) * math.pi * 1.0
    elif shape == 'inverted_conical':
        ratio = 1 - (water_level / capacity) if capacity > 0 else 0
        return (ratio ** 2) * math.pi * 1.0 + 0.1
    elif shape == 'spherical':
        r = (capacity * 3 / (4 * math.pi)) ** (1/3) if capacity > 0 else 1
        h = water_level
        if h >= 2 * r:
            h = 2 * r
        return math.pi * h * (2 * r - h)
    else:
        return 1.0


def get_orifice_area(orifice_diameter: float) -> float:
    return math.pi * (orifice_diameter / 2) ** 2


def calculate_flow_rate(water_level: float, orifice_diameter: float,
                        shape: str, capacity: float, shape_params: Optional[str] = None,
                        discharge_coefficient: float = 0.6) -> float:
    if water_level <= 0:
        return 0.0
    orifice_area = get_orifice_area(orifice_diameter)
    velocity = discharge_coefficient * math.sqrt(2 * GRAVITY * water_level)
    return orifice_area * velocity


def calculate_water_level_drop_rate(water_level: float, orifice_diameter: float,
                                     shape: str, capacity: float, shape_params: Optional[str] = None,
                                     discharge_coefficient: float = 0.6) -> float:
    if water_level <= 0:
        return 0.0
    container_area = get_cross_sectional_area(shape, water_level, capacity, shape_params)
    if container_area <= 0:
        return 0.0
    flow_rate = calculate_flow_rate(water_level, orifice_diameter, shape, capacity, shape_params, discharge_coefficient)
    return flow_rate / container_area


def simulate_water_curve(initial_water_level: float, orifice_diameter: float,
                         shape: str, capacity: float, shape_params: Optional[str] = None,
                         discharge_coefficient: float = 0.6,
                         time_step: float = 0.1, max_time: float = 100000.0) -> List[Tuple[float, float]]:
    results = []
    current_level = initial_water_level
    current_time = 0.0
    results.append((current_time, current_level))

    while current_level > 0.001 and current_time < max_time:
        drop_rate = calculate_water_level_drop_rate(
            current_level, orifice_diameter, shape, capacity, shape_params, discharge_coefficient
        )
        actual_step = min(time_step, current_level / max(drop_rate, 1e-10) if drop_rate > 0 else time_step)
        current_level -= drop_rate * actual_step
        current_time += actual_step
        if current_level < 0:
            current_level = 0
        results.append((round(current_time, 4), round(current_level, 6)))

    return results


def find_time_for_water_level(target_level: float, curve: List[Tuple[float, float]]) -> Optional[float]:
    if not curve:
        return None

    if curve[0][1] <= target_level:
        return curve[0][0]

    for i in range(1, len(curve)):
        prev_time, prev_level = curve[i - 1]
        curr_time, curr_level = curve[i]

        if prev_level >= target_level >= curr_level:
            if prev_level == curr_level:
                return prev_time
            ratio = (prev_level - target_level) / (prev_level - curr_level)
            return prev_time + ratio * (curr_time - prev_time)

    return curve[-1][0]


def find_water_level_for_time(target_time: float, curve: List[Tuple[float, float]]) -> Optional[float]:
    if not curve:
        return None

    if target_time <= curve[0][0]:
        return curve[0][1]

    for i in range(1, len(curve)):
        prev_time, prev_level = curve[i - 1]
        curr_time, curr_level = curve[i]

        if prev_time <= target_time <= curr_time:
            if prev_time == curr_time:
                return prev_level
            ratio = (target_time - prev_time) / (curr_time - prev_time)
            return prev_level + ratio * (curr_level - prev_level)

    return curve[-1][1]


def generate_scale_marks(scale_count: int, time_interval: float, initial_water_level: float,
                         orifice_diameter: float, shape: str, capacity: float,
                         shape_params: Optional[str] = None, error_threshold: float = 5.0,
                         discharge_coefficient: float = 0.6
                         ) -> List[Dict]:
    curve = simulate_water_curve(
        initial_water_level, orifice_diameter, shape, capacity, shape_params, discharge_coefficient
    )
    marks = []

    for i in range(scale_count + 1):
        theoretical_time = i * time_interval
        water_level = find_water_level_for_time(theoretical_time, curve)

        if water_level is not None:
            actual_time = find_time_for_water_level(water_level, curve) or theoretical_time
        else:
            actual_time = theoretical_time
            water_level = 0

        error = abs(actual_time - theoretical_time)

        marks.append({
            'scale_index': i,
            'theoretical_time': theoretical_time,
            'estimated_time': actual_time,
            'water_level': water_level,
            'error': error,
            'exceeds_threshold': error > error_threshold
        })

    return marks


def calculate_average_error(marks: List[Dict]) -> float:
    if not marks:
        return 0.0
    return sum(m['error'] for m in marks) / len(marks)


def calculate_max_error(marks: List[Dict]) -> float:
    if not marks:
        return 0.0
    return max(m['error'] for m in marks)


def interpolate_experimental_data(data_points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if len(data_points) < 2:
        return data_points

    sorted_points = sorted(data_points, key=lambda x: x[0])
    result = []
    for i in range(len(sorted_points) - 1):
        t1, l1 = sorted_points[i]
        t2, l2 = sorted_points[i + 1]
        steps = max(2, int((t2 - t1) / 0.5))
        for j in range(steps):
            ratio = j / steps
            t = t1 + ratio * (t2 - t1)
            l = l1 + ratio * (l2 - l1)
            result.append((round(t, 4), round(l, 6)))
    result.append(sorted_points[-1])
    return result


def calculate_rmse(experimental_points: List[Tuple[float, float]], simulated_curve: List[Tuple[float, float]]) -> float:
    if len(experimental_points) < 2:
        return float('inf')
    
    sum_squared_error = 0.0
    count = 0
    
    for exp_time, exp_level in experimental_points:
        sim_level = find_water_level_for_time(exp_time, simulated_curve)
        if sim_level is not None:
            error = exp_level - sim_level
            sum_squared_error += error ** 2
            count += 1
    
    if count == 0:
        return float('inf')
    
    return math.sqrt(sum_squared_error / count)


def calculate_mae(experimental_points: List[Tuple[float, float]], simulated_curve: List[Tuple[float, float]]) -> float:
    if len(experimental_points) < 2:
        return float('inf')
    
    sum_absolute_error = 0.0
    count = 0
    
    for exp_time, exp_level in experimental_points:
        sim_level = find_water_level_for_time(exp_time, simulated_curve)
        if sim_level is not None:
            error = abs(exp_level - sim_level)
            sum_absolute_error += error
            count += 1
    
    if count == 0:
        return float('inf')
    
    return sum_absolute_error / count


def calculate_r_squared(experimental_points: List[Tuple[float, float]], simulated_curve: List[Tuple[float, float]]) -> float:
    if len(experimental_points) < 2:
        return 0.0
    
    exp_levels = [level for _, level in experimental_points]
    mean_exp = sum(exp_levels) / len(exp_levels)
    
    ss_total = sum((level - mean_exp) ** 2 for level in exp_levels)
    ss_residual = 0.0
    
    for exp_time, exp_level in experimental_points:
        sim_level = find_water_level_for_time(exp_time, simulated_curve)
        if sim_level is not None:
            ss_residual += (exp_level - sim_level) ** 2
    
    if ss_total == 0:
        return 0.0
    
    return 1 - (ss_residual / ss_total)


def calibrate_parameters(
    experimental_points: List[Tuple[float, float]],
    initial_water_level: float,
    initial_orifice_diameter: float,
    shape: str,
    capacity: float,
    shape_params: Optional[str] = None
) -> Dict[str, Any]:
    best_params = {
        'orifice_diameter': initial_orifice_diameter,
        'discharge_coefficient': 0.6,
        'shape_params': shape_params,
        'rmse': float('inf'),
        'mae': float('inf'),
        'r_squared': 0.0
    }
    
    diameter_range = [initial_orifice_diameter * (0.5 + i * 0.05) for i in range(21)]
    coefficient_range = [0.3 + i * 0.03 for i in range(15)]
    
    for diam in diameter_range:
        for coeff in coefficient_range:
            curve = simulate_water_curve(
                initial_water_level, diam, shape, capacity, shape_params, coeff
            )
            rmse = calculate_rmse(experimental_points, curve)
            mae = calculate_mae(experimental_points, curve)
            r2 = calculate_r_squared(experimental_points, curve)
            
            if rmse < best_params['rmse']:
                best_params.update({
                    'orifice_diameter': diam,
                    'discharge_coefficient': coeff,
                    'rmse': rmse,
                    'mae': mae,
                    'r_squared': r2
                })
    
    return best_params


def generate_fitted_curve(
    calibrated_params: Dict[str, Any],
    initial_water_level: float,
    shape: str,
    capacity: float,
    shape_params: Optional[str] = None,
    time_step: float = 0.5
) -> List[Tuple[float, float]]:
    return simulate_water_curve(
        initial_water_level,
        calibrated_params['orifice_diameter'],
        shape,
        capacity,
        shape_params,
        calibrated_params['discharge_coefficient'],
        time_step
    )


def generate_candidate_schemes(
    calibrated_params: Dict[str, Any],
    initial_water_level: float,
    shape: str,
    capacity: float,
    shape_params: Optional[str] = None,
    candidate_count: int = 5,
    min_scale_count: int = 10,
    max_scale_count: int = 50,
    error_threshold: float = 5.0
) -> List[Dict[str, Any]]:
    candidates = []
    experiment_curve = generate_fitted_curve(
        calibrated_params, initial_water_level, shape, capacity, shape_params
    )
    
    if not experiment_curve:
        return []
    
    total_duration = experiment_curve[-1][0]
    
    scale_counts = []
    step = max(1, (max_scale_count - min_scale_count) // max(1, candidate_count - 1))
    for i in range(candidate_count):
        sc = min_scale_count + i * step
        if sc <= max_scale_count:
            scale_counts.append(sc)
    
    for idx, scale_count in enumerate(scale_counts):
        time_interval = total_duration / scale_count
        
        marks = generate_scale_marks(
            scale_count, time_interval, initial_water_level,
            calibrated_params['orifice_diameter'], shape, capacity, shape_params,
            error_threshold, calibrated_params['discharge_coefficient']
        )
        
        avg_error = calculate_average_error(marks)
        max_error = calculate_max_error(marks)
        exceeds_count = sum(1 for m in marks if m['exceeds_threshold'])
        
        candidates.append({
            'name': f'候选方案 {idx + 1}',
            'scale_count': scale_count,
            'time_interval': round(time_interval, 2),
            'error_threshold': error_threshold,
            'avg_error': round(avg_error, 4),
            'max_error': round(max_error, 4),
            'exceeds_count': exceeds_count,
            'marks': marks
        })
    
    candidates.sort(key=lambda x: (x['avg_error'], x['max_error'], x['exceeds_count']))
    
    for rank, candidate in enumerate(candidates, 1):
        candidate['rank'] = rank
        candidate['is_recommended'] = (rank == 1)
        candidate['name'] = f'候选方案 {rank} (刻度数:{candidate["scale_count"]})'
    
    return candidates


def detect_warning_segments(marks: List[Dict], error_threshold: float) -> List[Dict[str, Any]]:
    warnings = []
    
    for i, mark in enumerate(marks):
        if mark['exceeds_threshold']:
            severity = 'high' if mark['error'] > error_threshold * 2 else 'medium'
            
            warnings.append({
                'scale_index': mark['scale_index'],
                'start_time': mark['theoretical_time'],
                'end_time': marks[i + 1]['theoretical_time'] if i + 1 < len(marks) else mark['theoretical_time'],
                'error': mark['error'],
                'threshold': error_threshold,
                'severity': severity
            })
    
    return warnings


def generate_error_comparison(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    comparison = []
    
    for candidate in candidates:
        comparison.append({
            'rank': candidate['rank'],
            'name': candidate['name'],
            'scale_count': candidate['scale_count'],
            'time_interval': candidate['time_interval'],
            'avg_error': candidate['avg_error'],
            'max_error': candidate['max_error'],
            'exceeds_count': candidate['exceeds_count'],
            'is_recommended': candidate['is_recommended']
        })
    
    return comparison


# ============================================
# 多漏壶串联系统模拟与昼夜计时校正模块
# ============================================

SHICHEN_NAMES = [
    "子时", "丑时", "寅时", "卯时", "辰时", "巳时",
    "午时", "未时", "申时", "酉时", "戌时", "亥时"
]

SHICHEN_MODERN_HOURS = [
    (23, 1), (1, 3), (3, 5), (5, 7), (7, 9), (9, 11),
    (11, 13), (13, 15), (15, 17), (17, 19), (19, 21), (21, 23)
]

DYNASTY_FORMATS = {
    "han": {"name": "汉代", "shichen_count": 12, "subdivisions": 100, "unit": "刻"},
    "tang": {"name": "唐代", "shichen_count": 12, "subdivisions": 96, "unit": "刻"},
    "song": {"name": "宋代", "shichen_count": 12, "subdivisions": 96, "unit": "刻"},
    "ming": {"name": "明代", "shichen_count": 12, "subdivisions": 96, "unit": "刻"},
    "qing": {"name": "清代", "shichen_count": 12, "subdivisions": 96, "unit": "刻"},
    "modern": {"name": "现代（百刻制）", "shichen_count": 12, "subdivisions": 100, "unit": "刻"},
}


def get_viscosity_correction(temperature_c: float) -> float:
    t = max(0.0, min(temperature_c, 100.0))
    mu_20 = 1.002e-3
    mu_t = 1.002e-3 * math.exp(-0.025 * (t - 20))
    return mu_20 / mu_t


def generate_diurnal_temperature_curve(
    total_seconds: float,
    base_temp: float = 20.0,
    amplitude: float = 8.0,
    phase_offset: float = 0.0,
    points: int = 500
) -> List[Tuple[float, float]]:
    curve = []
    day_seconds = 24.0 * 3600.0
    for i in range(points + 1):
        t = (total_seconds * i) / points
        phase = 2 * math.pi * (t / day_seconds) + phase_offset
        temp = base_temp + amplitude * math.sin(phase - math.pi / 2)
        curve.append((round(t, 2), round(temp, 3)))
    return curve


def get_temperature_at_time(target_time: float, temp_curve: List[Tuple[float, float]]) -> float:
    if not temp_curve:
        return 20.0
    if target_time <= temp_curve[0][0]:
        return temp_curve[0][1]
    if target_time >= temp_curve[-1][0]:
        return temp_curve[-1][1]
    for i in range(1, len(temp_curve)):
        prev_t, prev_temp = temp_curve[i - 1]
        curr_t, curr_temp = temp_curve[i]
        if prev_t <= target_time <= curr_t:
            if prev_t == curr_t:
                return prev_temp
            ratio = (target_time - prev_t) / (curr_t - prev_t)
            return prev_temp + ratio * (curr_temp - prev_temp)
    return temp_curve[-1][1]


def simulate_series_system(
    stages: List[Dict[str, Any]],
    enable_temp_effect: bool = True,
    base_temperature: float = 20.0,
    temp_amplitude: float = 8.0,
    time_step: float = 0.5,
    max_time: float = 24.0 * 3600.0
) -> Dict[str, Any]:
    n = len(stages)
    if n == 0:
        return {"error": "至少需要一级漏壶"}

    current_levels = []
    for s in stages:
        init_level = s.get("initial_level_override")
        if init_level is None or init_level <= 0:
            init_level = s.get("initial_water_level", s.get("capacity", 100) * 0.8)
        init_level = min(init_level, s.get("capacity", 100))
        current_levels.append(init_level)

    stage_curves = [[] for _ in range(n)]
    for i in range(n):
        stage_curves[i].append((0.0, current_levels[i]))

    total_duration = 24.0 * 3600.0
    temp_curve = generate_diurnal_temperature_curve(total_duration, base_temperature, temp_amplitude)

    current_time = 0.0
    outflow_history = []

    while current_time < total_duration and current_levels[-1] > 0.001:
        current_temp = get_temperature_at_time(current_time, temp_curve) if enable_temp_effect else base_temperature
        viscosity_factor = get_viscosity_correction(current_temp) if enable_temp_effect else 1.0

        inflow_next = 0.0
        for i in range(n):
            stage = stages[i]
            od = stage.get("orifice_diameter_override")
            if od is None or od <= 0:
                od = stage.get("orifice_diameter", 0.5)
            shape = stage.get("shape", "cylindrical")
            capacity = stage.get("capacity", 100)
            shape_params = stage.get("shape_params")
            dc = stage.get("discharge_coefficient", 0.6)

            effective_level = current_levels[i]
            if i > 0:
                effective_level = max(0, current_levels[i])

            outflow_rate = calculate_flow_rate(
                effective_level, od, shape, capacity, shape_params, dc
            ) * viscosity_factor

            if i > 0:
                current_levels[i] += inflow_next * time_step

            drop_rate = 0.0
            container_area = get_cross_sectional_area(shape, current_levels[i], capacity, shape_params)
            if container_area > 0:
                drop_rate = outflow_rate / container_area

            actual_step = min(time_step, current_levels[i] / max(drop_rate, 1e-10) if drop_rate > 0 else time_step)
            current_levels[i] -= drop_rate * actual_step
            current_levels[i] = max(0.0, min(current_levels[i], capacity))

            if stage.get("is_refill_enabled", False):
                trigger = stage.get("refill_trigger_level", capacity * 0.2)
                target = stage.get("refill_target_level", capacity * 0.9)
                if current_levels[i] <= trigger:
                    current_levels[i] = target

            if i == n - 1:
                outflow_history.append((current_time, outflow_rate))

            inflow_next = outflow_rate

        current_time += actual_step
        for i in range(n):
            stage_curves[i].append((round(current_time, 2), round(current_levels[i], 6)))

    total_elapsed = current_time
    return {
        "stage_curves": stage_curves,
        "temp_curve": temp_curve,
        "total_duration": total_elapsed,
        "final_levels": current_levels,
        "outflow_history": outflow_history
    }


def generate_shichen_time_scheme(
    last_stage_curve: List[Tuple[float, float]],
    total_duration: float,
    shichen_count: int = 12,
    error_threshold: float = 30.0,
    dynasty_format: str = "modern"
) -> Dict[str, Any]:
    fmt = DYNASTY_FORMATS.get(dynasty_format, DYNASTY_FORMATS["modern"])
    effective_shichen = min(shichen_count, fmt["shichen_count"])

    shichen_duration = total_duration / effective_shichen
    marks = []
    error_curve = []

    for i in range(effective_shichen + 1):
        theoretical_time = i * shichen_duration
        water_level = find_water_level_for_time(theoretical_time, last_stage_curve)
        if water_level is None:
            water_level = 0.0
        actual_time = find_time_for_water_level(water_level, last_stage_curve) or theoretical_time
        error = actual_time - theoretical_time

        marks.append({
            "scale_index": i,
            "shichen_name": SHICHEN_NAMES[i] if i < effective_shichen else "终点",
            "shichen_hours": SHICHEN_MODERN_HOURS[i] if i < effective_shichen else (23, 23),
            "theoretical_time": theoretical_time,
            "estimated_time": actual_time,
            "water_level": water_level,
            "error": error,
            "abs_error": abs(error),
            "exceeds_threshold": abs(error) > error_threshold,
            "subdivision_count": fmt["subdivisions"],
            "subdivision_unit": fmt["unit"]
        })
        error_curve.append({"time": theoretical_time, "error": error})

    errors = [m["abs_error"] for m in marks]
    total_error = sum(errors)
    avg_error = total_error / len(errors) if errors else 0.0
    max_error = max(errors) if errors else 0.0

    warnings = detect_warning_segments(marks, error_threshold)

    recommendations = generate_correction_recommendations(marks, warnings, total_duration, effective_shichen)

    return {
        "marks": marks,
        "error_curve": error_curve,
        "total_error": round(total_error, 4),
        "avg_error": round(avg_error, 4),
        "max_error": round(max_error, 4),
        "warning_segments": warnings,
        "recommendations": recommendations,
        "dynasty": fmt["name"],
        "subdivision_unit": fmt["unit"],
        "subdivisions_per_shichen": fmt["subdivisions"]
    }


def generate_correction_recommendations(
    marks: List[Dict],
    warnings: List[Dict],
    total_duration: float,
    shichen_count: int
) -> List[Dict[str, Any]]:
    recommendations = []
    errors = [m["error"] for m in marks]
    cumulative_error = errors[-1] if errors else 0

    if abs(cumulative_error) > 60:
        direction = "偏快" if cumulative_error < 0 else "偏慢"
        recommendations.append({
            "type": "critical",
            "priority": 1,
            "title": "累计计时误差过大",
            "description": f"全周期累计误差 {abs(cumulative_error):.1f} 秒，系统整体{direction}。",
            "action": "建议调整最末级出流孔径：偏快则减小孔径，偏慢则增大孔径，或调整初始水位。"
        })
    elif abs(cumulative_error) > 30:
        direction = "偏快" if cumulative_error < 0 else "偏慢"
        recommendations.append({
            "type": "warning",
            "priority": 2,
            "title": "累计计时偏差明显",
            "description": f"全周期累计误差 {abs(cumulative_error):.1f} 秒，系统{direction}。",
            "action": "建议微调最末级出流孔径或提高补水目标水位。"
        })

    if warnings:
        high_warns = [w for w in warnings if w.get("severity") == "high"]
        if high_warns:
            recommendations.append({
                "type": "warning",
                "priority": 2,
                "title": f"存在 {len(high_warns)} 处高危误差段",
                "description": f"以下时段误差超阈值两倍：{', '.join(str(w['scale_index']) for w in high_warns)}",
                "action": "建议在对应时段前增加补水操作，或检查串联级间连接是否通畅。"
            })

    if len(marks) > 1:
        err_trend = []
        for i in range(1, len(marks)):
            err_trend.append(marks[i]["error"] - marks[i - 1]["error"])
        avg_trend = sum(err_trend) / len(err_trend) if err_trend else 0
        if abs(avg_trend) > 1:
            recommendations.append({
                "type": "info",
                "priority": 3,
                "title": "误差呈单调性趋势",
                "description": "误差随时间持续累积，可能是补水机制不足或水位衰减过快。",
                "action": "建议启用中间级自动补水，或调整补水触发阈值。"
            })

    if not recommendations:
        recommendations.append({
            "type": "success",
            "priority": 5,
            "title": "系统计时精度良好",
            "description": f"12时辰累计误差 {abs(cumulative_error):.1f} 秒，各时辰误差均在阈值内。",
            "action": "可直接采用此刻度方案，建议每日校准一次最末级水位。"
        })

    recommendations.sort(key=lambda r: r["priority"])
    return recommendations


def generate_dynasty_export(
    scheme: Dict[str, Any],
    system: Dict[str, Any],
    stages: List[Dict[str, Any]],
    dynasty_format: str = "modern"
) -> Dict[str, Any]:
    fmt = DYNASTY_FORMATS.get(dynasty_format, DYNASTY_FORMATS["modern"])
    marks = scheme["marks"]
    subdivisions = fmt["subdivisions"]
    unit = fmt["unit"]

    detailed_marks = []
    for m in marks:
        sub_marks = []
        if m["scale_index"] < len(marks) - 1:
            next_m = marks[m["scale_index"] + 1]
            for k in range(subdivisions):
                ratio = k / subdivisions
                sub_marks.append({
                    "sub_index": k,
                    "water_level": m["water_level"] + ratio * (next_m["water_level"] - m["water_level"]),
                    "theoretical_time": m["theoretical_time"] + ratio * (next_m["theoretical_time"] - m["theoretical_time"])
                })
        detailed_marks.append({
            "shichen": m["shichen_name"],
            "modern_hours": m["shichen_hours"],
            "water_level": m["water_level"],
            "theoretical_time_sec": m["theoretical_time"],
            "error_sec": m["error"],
            "subdivisions": sub_marks,
            "subdivision_unit": unit,
            "subdivision_count": subdivisions
        })

    return {
        "dynasty": fmt["name"],
        "dynasty_key": dynasty_format,
        "system_name": system.get("name", ""),
        "total_stages": len(stages),
        "shichen_count": fmt["shichen_count"],
        "subdivision_unit": unit,
        "subdivisions_per_shichen": subdivisions,
        "total_duration_hours": scheme.get("total_duration", 0) / 3600.0,
        "total_error_sec": scheme.get("total_error", 0),
        "avg_error_sec": scheme.get("avg_error", 0),
        "max_error_sec": scheme.get("max_error", 0),
        "shichen_marks": detailed_marks,
        "stages": stages,
        "generated_at": None
    }


def calculate_statistics(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "median": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "cv": 0.0}
    
    n = len(values)
    mean_val = sum(values) / n
    
    sorted_vals = sorted(values)
    if n % 2 == 0:
        median_val = (sorted_vals[n//2 - 1] + sorted_vals[n//2]) / 2
    else:
        median_val = sorted_vals[n//2]
    
    variance = sum((v - mean_val) ** 2 for v in values) / max(1, n)
    std_val = math.sqrt(variance)
    cv_val = (std_val / abs(mean_val) * 100) if mean_val != 0 else 0.0
    
    return {
        "mean": mean_val,
        "median": median_val,
        "std": std_val,
        "min": min(values),
        "max": max(values),
        "cv": cv_val
    }


def robust_mean(values: List[float], trim_percent: float = 0.2) -> float:
    if not values:
        return 0.0
    
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    trim_count = int(n * trim_percent)
    
    if trim_count * 2 >= n:
        return calculate_statistics(values)["median"]
    
    trimmed = sorted_vals[trim_count:n - trim_count]
    return sum(trimmed) / len(trimmed)


def multi_source_calibrate(
    experiments_data: List[Dict[str, Any]],
    initial_water_level: float,
    initial_orifice_diameter: float,
    shape: str,
    capacity: float,
    shape_params: Optional[str] = None,
    calibration_method: str = "weighted_average"
) -> Dict[str, Any]:
    if not experiments_data:
        raise ValueError("至少需要一组实验数据")
    
    fitting_results = []
    
    for exp_data in experiments_data:
        exp_points = exp_data["points"]
        weight = exp_data.get("weight", 1.0)
        is_included = exp_data.get("is_included", True)
        
        if not is_included or len(exp_points) < 2:
            continue
        
        result = calibrate_parameters(
            exp_points,
            initial_water_level,
            initial_orifice_diameter,
            shape,
            capacity,
            shape_params
        )
        
        fitted_curve = generate_fitted_curve(
            result, initial_water_level, shape, capacity, shape_params
        )
        
        fitting_results.append({
            "experiment_id": exp_data.get("experiment_id"),
            "experiment_name": exp_data.get("experiment_name"),
            "weight": weight,
            "calibrated_orifice_diameter": result["orifice_diameter"],
            "calibrated_discharge_coefficient": result["discharge_coefficient"],
            "rmse": result["rmse"],
            "mae": result["mae"],
            "r_squared": result["r_squared"],
            "fitting_curve": [{"time": t, "level": l} for t, l in fitted_curve]
        })
    
    if not fitting_results:
        raise ValueError("没有有效的实验数据可以进行校准")
    
    orifice_diameters = [r["calibrated_orifice_diameter"] for r in fitting_results]
    discharge_coefficients = [r["calibrated_discharge_coefficient"] for r in fitting_results]
    weights = [r["weight"] for r in fitting_results]
    
    if calibration_method == "weighted_average":
        total_weight = sum(weights)
        combined_orifice = sum(d * w for d, w in zip(orifice_diameters, weights)) / total_weight
        combined_coeff = sum(d * w for d, w in zip(discharge_coefficients, weights)) / total_weight
    elif calibration_method == "mean":
        combined_orifice = sum(orifice_diameters) / len(orifice_diameters)
        combined_coeff = sum(discharge_coefficients) / len(discharge_coefficients)
    elif calibration_method == "median":
        combined_orifice = calculate_statistics(orifice_diameters)["median"]
        combined_coeff = calculate_statistics(discharge_coefficients)["median"]
    elif calibration_method == "robust_mean":
        combined_orifice = robust_mean(orifice_diameters)
        combined_coeff = robust_mean(discharge_coefficients)
    else:
        combined_orifice = sum(orifice_diameters) / len(orifice_diameters)
        combined_coeff = sum(discharge_coefficients) / len(discharge_coefficients)
    
    return {
        "fitting_results": fitting_results,
        "combined_params": {
            "orifice_diameter": round(combined_orifice, 6),
            "discharge_coefficient": round(combined_coeff, 6),
            "shape_params": shape_params
        },
        "parameter_statistics": {
            "orifice_diameter": calculate_statistics(orifice_diameters),
            "discharge_coefficient": calculate_statistics(discharge_coefficients)
        },
        "calibration_method": calibration_method
    }


def analyze_consistency(
    fitting_results: List[Dict[str, Any]],
    cv_threshold: float = 10.0
) -> Dict[str, Any]:
    if len(fitting_results) < 2:
        return {
            "overall_consistency_score": 100.0,
            "parameter_consistency": {},
            "metric_consistency": {},
            "outlier_experiments": [],
            "conclusion": "仅一组实验数据，无需一致性分析"
        }
    
    orifice_diameters = [r["calibrated_orifice_diameter"] for r in fitting_results]
    discharge_coefficients = [r["calibrated_discharge_coefficient"] for r in fitting_results]
    rmses = [r["rmse"] for r in fitting_results]
    maes = [r["mae"] for r in fitting_results]
    r_squareds = [r["r_squared"] for r in fitting_results]
    
    orifice_stats = calculate_statistics(orifice_diameters)
    coeff_stats = calculate_statistics(discharge_coefficients)
    rmse_stats = calculate_statistics(rmses)
    mae_stats = calculate_statistics(maes)
    r2_stats = calculate_statistics(r_squareds)
    
    parameter_consistency = {
        "orifice_diameter": {
            "values": orifice_diameters,
            "stats": orifice_stats,
            "consistent": orifice_stats["cv"] < cv_threshold,
            "consistency_score": max(0, 100 - orifice_stats["cv"])
        },
        "discharge_coefficient": {
            "values": discharge_coefficients,
            "stats": coeff_stats,
            "consistent": coeff_stats["cv"] < cv_threshold,
            "consistency_score": max(0, 100 - coeff_stats["cv"])
        }
    }
    
    metric_consistency = {
        "rmse": {"values": rmses, "stats": rmse_stats, "consistency_score": max(0, 100 - rmse_stats["cv"])},
        "mae": {"values": maes, "stats": mae_stats, "consistency_score": max(0, 100 - mae_stats["cv"])},
        "r_squared": {"values": r_squareds, "stats": r2_stats, "consistency_score": max(0, min(100, r2_stats["mean"] * 100))}
    }
    
    outlier_experiments = []
    for i, result in enumerate(fitting_results):
        is_outlier = False
        outlier_reasons = []
        
        if abs(result["calibrated_orifice_diameter"] - orifice_stats["mean"]) > 2 * orifice_stats["std"]:
            is_outlier = True
            outlier_reasons.append("孔径参数偏离均值超过2倍标准差")
        
        if abs(result["calibrated_discharge_coefficient"] - coeff_stats["mean"]) > 2 * coeff_stats["std"]:
            is_outlier = True
            outlier_reasons.append("流量系数偏离均值超过2倍标准差")
        
        if result["r_squared"] < 0.9:
            is_outlier = True
            outlier_reasons.append(f"拟合优度R²过低({result['r_squared']:.4f})")
        
        if is_outlier:
            outlier_experiments.append({
                "experiment_id": result.get("experiment_id"),
                "experiment_name": result.get("experiment_name"),
                "reasons": outlier_reasons
            })
    
    param_scores = [parameter_consistency[k]["consistency_score"] for k in parameter_consistency]
    metric_scores = [metric_consistency[k]["consistency_score"] for k in metric_consistency]
    overall_score = (sum(param_scores) + sum(metric_scores)) / (len(param_scores) + len(metric_scores))
    
    if overall_score >= 90:
        conclusion = "多源实验数据一致性优秀，参数拟合结果稳定可靠"
    elif overall_score >= 75:
        conclusion = "多源实验数据一致性良好，参数拟合结果较为可靠"
    elif overall_score >= 60:
        conclusion = "多源实验数据一致性一般，建议检查异常实验数据"
    else:
        conclusion = "多源实验数据一致性较差，存在显著异常值，建议重新进行实验"
    
    return {
        "overall_consistency_score": round(overall_score, 2),
        "parameter_consistency": parameter_consistency,
        "metric_consistency": metric_consistency,
        "outlier_experiments": outlier_experiments,
        "analysis_details": {
            "experiment_count": len(fitting_results),
            "cv_threshold": cv_threshold
        },
        "conclusion": conclusion
    }


def generate_multi_source_candidate_schemes(
    combined_params: Dict[str, Any],
    initial_water_level: float,
    shape: str,
    capacity: float,
    shape_params: Optional[str],
    candidate_count: int = 5,
    min_scale_count: int = 10,
    max_scale_count: int = 50,
    error_threshold: float = 5.0
) -> List[Dict[str, Any]]:
    candidates = []
    experiment_curve = generate_fitted_curve(
        combined_params, initial_water_level, shape, capacity, shape_params
    )
    
    if not experiment_curve:
        return []
    
    total_duration = experiment_curve[-1][0]
    
    scale_counts = []
    step = max(1, (max_scale_count - min_scale_count) // max(1, candidate_count - 1))
    for i in range(candidate_count):
        sc = min_scale_count + i * step
        if sc <= max_scale_count:
            scale_counts.append(sc)
    
    for idx, scale_count in enumerate(scale_counts):
        time_interval = total_duration / scale_count
        
        marks = generate_scale_marks(
            scale_count, time_interval, initial_water_level,
            combined_params['orifice_diameter'], shape, capacity, shape_params,
            error_threshold, combined_params['discharge_coefficient']
        )
        
        avg_error = calculate_average_error(marks)
        max_error = calculate_max_error(marks)
        exceeds_count = sum(1 for m in marks if m['exceeds_threshold'])
        
        error_score = 100 - min(100, (avg_error / max(error_threshold, 0.1)) * 50)
        exceed_score = max(0, 100 - exceeds_count * 10)
        density_score = 100 - min(50, abs(scale_count - (min_scale_count + max_scale_count) / 2) / max(1, (max_scale_count - min_scale_count) / 2) * 50)
        
        overall_score = (error_score * 0.5 + exceed_score * 0.3 + density_score * 0.2)
        
        candidates.append({
            'name': f'联合校准方案 {idx + 1}',
            'scale_count': scale_count,
            'time_interval': round(time_interval, 2),
            'error_threshold': error_threshold,
            'combined_orifice_diameter': combined_params['orifice_diameter'],
            'combined_discharge_coefficient': combined_params['discharge_coefficient'],
            'avg_error': round(avg_error, 4),
            'max_error': round(max_error, 4),
            'exceeds_count': exceeds_count,
            'overall_score': round(overall_score, 2),
            'marks': marks
        })
    
    candidates.sort(key=lambda x: (-x['overall_score'], x['avg_error'], x['max_error']))
    
    for rank, candidate in enumerate(candidates, 1):
        candidate['rank'] = rank
        candidate['name'] = f'联合校准方案 {rank} (刻度数:{candidate["scale_count"]}, 评分:{candidate["overall_score"]:.1f})'
    
    return candidates


def aggregate_expert_scores(
    expert_scores: List[Dict[str, Any]]
) -> Dict[str, Any]:
    if not expert_scores:
        return {
            "avg_accuracy_score": 0.0,
            "avg_feasibility_score": 0.0,
            "avg_historical_score": 0.0,
            "avg_overall_score": 0.0,
            "expert_count": 0,
            "score_distribution": {},
            "comments_summary": []
        }
    
    accuracy_scores = [s["accuracy_score"] for s in expert_scores]
    feasibility_scores = [s["feasibility_score"] for s in expert_scores]
    historical_scores = [s["historical_consistency_score"] for s in expert_scores]
    overall_scores = [s["overall_score"] for s in expert_scores]
    comments = [s.get("comments", "") for s in expert_scores if s.get("comments")]
    
    def score_distribution(scores):
        dist = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
        for s in scores:
            if s >= 90:
                dist["excellent"] += 1
            elif s >= 75:
                dist["good"] += 1
            elif s >= 60:
                dist["fair"] += 1
            else:
                dist["poor"] += 1
        return dist
    
    return {
        "avg_accuracy_score": round(sum(accuracy_scores) / len(accuracy_scores), 2),
        "avg_feasibility_score": round(sum(feasibility_scores) / len(feasibility_scores), 2),
        "avg_historical_score": round(sum(historical_scores) / len(historical_scores), 2),
        "avg_overall_score": round(sum(overall_scores) / len(overall_scores), 2),
        "expert_count": len(expert_scores),
        "score_distribution": score_distribution(overall_scores),
        "comments_summary": comments
    }


def compare_versions(
    version1_data: Dict[str, Any],
    version2_data: Dict[str, Any]
) -> Dict[str, Any]:
    differences = {}
    all_keys = set(version1_data.keys()) | set(version2_data.keys())
    
    for key in all_keys:
        v1 = version1_data.get(key)
        v2 = version2_data.get(key)
        
        if v1 != v2:
            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                diff = v2 - v1
                pct_diff = (diff / abs(v1) * 100) if v1 != 0 else float('inf')
                differences[key] = {
                    "old_value": v1,
                    "new_value": v2,
                    "absolute_diff": diff,
                    "percentage_diff": round(pct_diff, 2)
                }
            else:
                differences[key] = {
                    "old_value": v1,
                    "new_value": v2
                }
    
    numeric_diffs = []
    for key, diff in differences.items():
        if "percentage_diff" in diff and diff["percentage_diff"] != float('inf'):
            numeric_diffs.append(abs(diff["percentage_diff"]))
    
    if numeric_diffs:
        avg_pct_diff = sum(numeric_diffs) / len(numeric_diffs)
        similarity_score = max(0, 100 - avg_pct_diff)
    else:
        similarity_score = 100.0 if not differences else 50.0
    
    return {
        "differences": differences,
        "similarity_score": round(similarity_score, 2),
        "change_count": len(differences)
    }


def generate_review_report_content(
    calibration: Dict[str, Any],
    experiments: List[Dict[str, Any]],
    fitting_results: List[Dict[str, Any]],
    consistency_analysis: Optional[Dict[str, Any]],
    candidate_schemes: List[Dict[str, Any]],
    expert_reviews: List[Dict[str, Any]],
    scheme_eliminations: List[Dict[str, Any]],
    version_records: List[Dict[str, Any]],
    report_type: str = "full"
) -> Dict[str, Any]:
    active_schemes = [s for s in candidate_schemes if not s.get("is_eliminated", False)]
    eliminated_schemes = [s for s in candidate_schemes if s.get("is_eliminated", False)]
    final_scheme = next((s for s in candidate_schemes if s.get("is_final", False)), None)
    
    approved_reviews = [r for r in expert_reviews if r.get("review_result") == "approved"]
    rejected_reviews = [r for r in expert_reviews if r.get("review_result") == "rejected"]
    
    summary = {
        "calibration_name": calibration.get("name"),
        "calibration_method": calibration.get("calibration_method"),
        "status": calibration.get("status"),
        "is_locked": calibration.get("is_locked"),
        "experiment_count": len(experiments),
        "fitting_result_count": len(fitting_results),
        "total_candidate_schemes": len(candidate_schemes),
        "active_schemes": len(active_schemes),
        "eliminated_schemes": len(eliminated_schemes),
        "expert_review_count": len(expert_reviews),
        "approved_reviews": len(approved_reviews),
        "rejected_reviews": len(rejected_reviews),
        "version_count": len(version_records),
        "has_final_scheme": final_scheme is not None,
        "consistency_score": consistency_analysis.get("overall_consistency_score") if consistency_analysis else None
    }
    
    if report_type == "summary":
        return {
            "report_type": "summary",
            "summary": summary,
            "final_scheme": {
                "id": final_scheme["id"],
                "name": final_scheme["name"],
                "scale_count": final_scheme["scale_count"],
                "avg_error": final_scheme["avg_error"],
                "overall_score": final_scheme["overall_score"]
            } if final_scheme else None,
            "conclusion": consistency_analysis.get("conclusion") if consistency_analysis else None
        }
    
    elif report_type == "technical":
        return {
            "report_type": "technical",
            "summary": summary,
            "fitting_results": [{
                "experiment_id": fr.get("experiment_id"),
                "experiment_name": fr.get("experiment_name"),
                "orifice_diameter": fr.get("calibrated_orifice_diameter"),
                "discharge_coefficient": fr.get("calibrated_discharge_coefficient"),
                "rmse": fr.get("rmse"),
                "mae": fr.get("mae"),
                "r_squared": fr.get("r_squared")
            } for fr in fitting_results],
            "consistency_analysis": consistency_analysis,
            "candidate_schemes": [{
                "id": cs.get("id"),
                "name": cs.get("name"),
                "scale_count": cs.get("scale_count"),
                "time_interval": cs.get("time_interval"),
                "avg_error": cs.get("avg_error"),
                "max_error": cs.get("max_error"),
                "exceeds_count": cs.get("exceeds_count"),
                "overall_score": cs.get("overall_score"),
                "rank": cs.get("rank"),
                "is_eliminated": cs.get("is_eliminated"),
                "is_final": cs.get("is_final")
            } for cs in candidate_schemes]
        }
    
    elif report_type == "expert_review":
        return {
            "report_type": "expert_review",
            "summary": summary,
            "expert_reviews": [{
                "expert_name": er.get("expert_name"),
                "review_result": er.get("review_result"),
                "overall_comments": er.get("overall_comments"),
                "recommendations": er.get("recommendations"),
                "reviewed_at": er.get("reviewed_at")
            } for er in expert_reviews],
            "scheme_eliminations": [{
                "candidate_scheme_name": se.get("candidate_scheme_name"),
                "eliminated_by": se.get("eliminated_by"),
                "elimination_reason": se.get("elimination_reason"),
                "elimination_criteria": se.get("elimination_criteria")
            } for se in scheme_eliminations]
        }
    
    else:
        return {
            "report_type": "full",
            "summary": summary,
            "experiments": [{
                "id": exp.get("id"),
                "name": exp.get("name"),
                "data_point_count": exp.get("data_point_count"),
                "weight": exp.get("weight"),
                "is_included": exp.get("is_included")
            } for exp in experiments],
            "fitting_results": fitting_results,
            "consistency_analysis": consistency_analysis,
            "candidate_schemes": candidate_schemes,
            "expert_reviews": expert_reviews,
            "scheme_eliminations": scheme_eliminations,
            "version_records": version_records,
            "final_scheme": final_scheme,
            "institutional_review_conclusion": generate_institutional_review_conclusion(
                summary, consistency_analysis, expert_reviews, final_scheme
            )
        }


def generate_institutional_review_conclusion(
    summary: Dict[str, Any],
    consistency_analysis: Optional[Dict[str, Any]],
    expert_reviews: List[Dict[str, Any]],
    final_scheme: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    conclusions = []
    recommendations = []
    
    consistency_score = summary.get("consistency_score", 0)
    if consistency_score >= 90:
        conclusions.append("多源实验数据一致性优秀，为刻度复原提供了坚实的数据基础")
    elif consistency_score >= 75:
        conclusions.append("多源实验数据一致性良好，满足刻度复原的基本要求")
    elif consistency_score >= 60:
        conclusions.append("多源实验数据一致性一般，建议在后续实验中进一步验证")
        recommendations.append("建议补充更多在不同环境条件下的实验数据")
    else:
        conclusions.append("多源实验数据一致性较差，当前结果仅供参考")
        recommendations.append("强烈建议重新进行校准实验，确保数据质量")
    
    if summary["expert_review_count"] >= 3:
        approval_rate = summary["approved_reviews"] / summary["expert_review_count"]
        if approval_rate >= 0.8:
            conclusions.append(f"专家评审通过率达到{approval_rate*100:.0f}%，评审意见高度一致")
        elif approval_rate >= 0.6:
            conclusions.append(f"专家评审通过率为{approval_rate*100:.0f}%，基本达成共识")
        else:
            conclusions.append(f"专家评审通过率仅为{approval_rate*100:.0f}%，存在较大分歧")
            recommendations.append("建议组织进一步的专家论证会")
    elif summary["expert_review_count"] > 0:
        conclusions.append(f"已完成{summary['expert_review_count']}份专家评审，建议邀请更多专家参与评审")
        recommendations.append("建议至少邀请3位专家完成评审，确保评审结论的权威性")
    else:
        conclusions.append("尚未进行专家评审")
        recommendations.append("请尽快组织专家评审")
    
    if final_scheme:
        conclusions.append(f"已选定最终方案：{final_scheme.get('name')}")
        if summary.get("is_locked"):
            conclusions.append("最终方案已锁定，可用于正式刻度复原")
        else:
            recommendations.append("建议尽快完成最终方案的锁定流程")
    else:
        conclusions.append("尚未选定最终方案")
        recommendations.append("请从候选方案中选定最终方案并完成锁定")
    
    overall_status = "approved" if (
        consistency_score >= 75 and
        summary["approved_reviews"] >= 2 and
        final_scheme is not None
    ) else "pending" if summary["expert_review_count"] < 2 else "needs_revision"
    
    return {
        "overall_status": overall_status,
        "conclusions": conclusions,
        "recommendations": recommendations,
        "review_completeness": {
            "has_consistency_analysis": consistency_analysis is not None,
            "expert_review_count": summary["expert_review_count"],
            "has_final_scheme": final_scheme is not None,
            "is_locked": summary.get("is_locked", False)
        }
    }

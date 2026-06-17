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

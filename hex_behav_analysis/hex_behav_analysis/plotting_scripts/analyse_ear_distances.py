import numpy as np
from datetime import datetime
from collections import defaultdict
from scipy import stats


def analyse_ear_distances(
    sessions_input,
    likelihood_threshold=0.6,
    min_trial_duration=None,
    exclusion_mice=(),
    cue_modes=('all_trials',),
    image_width=None,
    image_height=None,
    verbose=True,
    statistical_test='auto',
):
    """
    Analyse the difference in distances between left and right ear coordinates from the image centre.
    
    For each trial, calculates the distance of each ear from the image centre, then computes
    the difference (right ear distance - left ear distance). A positive value indicates the
    right ear is further from the centre than the left ear.
    
    Additionally calculates the "tilt angle" of the ear-to-ear line, which measures how much
    the line between the ears deviates from what it should be if both ears were equidistant
    from the centre. This provides a geometric measure of head asymmetry.
    
    Parameters
    ----------
    sessions_input : list[Session] | dict[str, list[Session]]
        Either a list of Session objects or a dictionary mapping dataset names to session lists.
        When providing a dictionary (e.g., {'control': sessions1, 'treatment': sessions2}),
        the function will perform statistical comparisons between datasets.
    likelihood_threshold : float
        Minimum ear-tracking likelihood required for inclusion (0-1)
    min_trial_duration : float | None
        Minimum trial duration in seconds; trials shorter than this are excluded
    exclusion_mice : tuple[str, ...]
        Mouse IDs to exclude from analysis
    cue_modes : tuple[str, ...] | list[str]
        Trial types to analyse: ('all_trials', 'visual_trials', 'audio_trials')
    image_width : float | None
        Width of the tracking image in pixels. If None, uses 1280 (standard for behaviour videos)
    image_height : float | None
        Height of the tracking image in pixels. If None, uses 1080 (standard for behaviour videos)
    verbose : bool
        Whether to print detailed diagnostic information
    statistical_test : str
        Type of statistical test for comparisons: 'auto', 'ttest', 'mannwhitney'
        'auto' selects based on normality tests
        
    Returns
    -------
    dict
        Dictionary containing analysis results:
        - 'datasets': dict[str, dict] - Results for each dataset (if dict input)
        - 'comparisons': dict - Statistical comparisons between datasets (if dict input)
        - 'by_mode': dict[str, list[float]] - Distance differences by trial type (if list input)
        - 'by_mouse': dict[str, dict[str, list[dict]]] - Full trial data by mouse and mode
        - 'excluded': dict[str, int] - Count of excluded trials by reason
        - 'session_count': int - Total number of sessions processed
        - 'mouse_session_counts': dict[str, int] - Sessions per mouse
        - 'image_dimensions': tuple[float, float] - (width, height) used for analysis
        
    Notes
    -----
    The function extracts ear coordinates from trial['DLC_data'] DataFrames:
    - Left ear: trial['DLC_data']['left_ear']['x'], trial['DLC_data']['left_ear']['y']
    - Right ear: trial['DLC_data']['right_ear']['x'], trial['DLC_data']['right_ear']['y']
    - Likelihoods are extracted from trial['turn_data'] if available
    
    Tilt angle calculation:
    - 0° = ears are perfectly aligned (perpendicular to radial direction from centre)
    - Positive angles = clockwise tilt (when viewed from above)
    - Negative angles = counter-clockwise tilt
    - Range is [-90°, 90°] as ears cannot be tilted more than 90° in either direction
    
    When dictionary input is provided, performs statistical comparisons between datasets
    using t-tests or Mann-Whitney U tests, and calculates effect sizes (Cohen's d).
    """
    # Convert cue_modes to tuple if it's a list
    if isinstance(cue_modes, list):
        cue_modes = tuple(cue_modes)
    
    # Normalise session input format
    is_dict_input = isinstance(sessions_input, dict)
    if is_dict_input:
        if len(sessions_input) == 0:
            raise ValueError("Dictionary input must contain at least one dataset")
        sessions_dict = sessions_input
    else:
        sessions_dict = {'Dataset': sessions_input}
    
    # Process each dataset
    all_results = {}
    
    for dataset_name, sessions in sessions_dict.items():
        # Initialise data structures for this dataset
        ear_differences_by_mode = {mode: [] for mode in cue_modes}
        ear_differences_by_mouse = defaultdict(lambda: {mode: [] for mode in cue_modes})
        
        # Track exclusions
        excluded = {
            'catch': 0,
            'no_turn_data': 0,
            'low_likelihood': 0,
            'too_quick': 0,
            'missing_ear_data': 0,
            'angle_corrected': 0,
        }
        
        # Track sessions and mice
        session_count = 0
        mouse_session_counts = defaultdict(int)
        
        # Process all sessions in this dataset
        for session in sessions:
            session_count += 1
            mouse_id = session.session_dict.get('mouse_id', 'unknown')
            mouse_session_counts[mouse_id] += 1
            
            if mouse_id in exclusion_mice:
                continue
            
            # Process each trial
            for trial in session.trials:
                # Apply exclusion criteria
                if trial.get('catch'):
                    excluded['catch'] += 1
                    continue
                
                if trial.get('turn_data') is None:
                    excluded['no_turn_data'] += 1
                    continue
                
                turn_data = trial['turn_data']
                
                # Check for angle correction
                angle_method = turn_data.get('angle_correction_method', 'none')
                if angle_method != 'none':
                    excluded['angle_corrected'] += 1
                    continue
                
                # Check ear tracking likelihood
                left_likelihood = turn_data.get('left_ear_likelihood', 1.0)
                right_likelihood = turn_data.get('right_ear_likelihood', 1.0)
                if left_likelihood < likelihood_threshold or right_likelihood < likelihood_threshold:
                    excluded['low_likelihood'] += 1
                    continue
                
                # Check trial duration if specified
                if min_trial_duration is not None:
                    cue_start = trial.get('cue_start')
                    sensor_start = trial.get('next_sensor', {}).get('sensor_start')
                    if cue_start is not None and sensor_start is not None:
                        if sensor_start - cue_start < min_trial_duration:
                            excluded['too_quick'] += 1
                            continue
                
                # Extract ear coordinates from DLC data
                buffer = 1  # Match the default from find_angles method
                
                # Check if DLC data exists and has enough frames
                dlc_data = trial.get('DLC_data')
                if dlc_data is None or len(dlc_data) < buffer:
                    excluded['missing_ear_data'] += 1
                    continue
                
                # Extract and average ear coordinates over buffer frames
                try:
                    left_x_vals = []
                    left_y_vals = []
                    right_x_vals = []
                    right_y_vals = []
                    
                    for i in range(buffer):
                        # Extract coordinates for this frame
                        left_x = dlc_data["left_ear"]["x"].iloc[i]
                        left_y = dlc_data["left_ear"]["y"].iloc[i]
                        right_x = dlc_data["right_ear"]["x"].iloc[i]
                        right_y = dlc_data["right_ear"]["y"].iloc[i]
                        
                        # Check for valid values (not NaN or infinite)
                        if np.isfinite(left_x) and np.isfinite(left_y):
                            left_x_vals.append(left_x)
                            left_y_vals.append(left_y)
                        
                        if np.isfinite(right_x) and np.isfinite(right_y):
                            right_x_vals.append(right_x)
                            right_y_vals.append(right_y)
                    
                    # Ensure we have valid data
                    if not left_x_vals or not left_y_vals or not right_x_vals or not right_y_vals:
                        excluded['missing_ear_data'] += 1
                        continue
                    
                    # Calculate average coordinates
                    left_x = sum(left_x_vals) / len(left_x_vals)
                    left_y = sum(left_y_vals) / len(left_y_vals)
                    right_x = sum(right_x_vals) / len(right_x_vals)
                    right_y = sum(right_y_vals) / len(right_y_vals)
                    
                except (KeyError, IndexError, AttributeError) as e:
                    # Handle cases where the expected structure is not present
                    excluded['missing_ear_data'] += 1
                    continue
                
                # Determine image dimensions if not provided
                if image_width is None or image_height is None:
                    # Use the typical dimensions from the Session class
                    img_width = 1280.0  # Standard width from Session.draw_LEDs
                    img_height = 1080.0  # Standard height from Session.draw_LEDs
                else:
                    img_width = image_width
                    img_height = image_height
                
                # Calculate image centre
                centre_x = img_width / 2.0
                centre_y = img_height / 2.0
                
                # Calculate distances from centre
                left_distance = np.sqrt((left_x - centre_x)**2 + (left_y - centre_y)**2)
                right_distance = np.sqrt((right_x - centre_x)**2 + (right_y - centre_y)**2)
                
                # Calculate difference (positive if right ear is further)
                distance_diff = right_distance - left_distance
                
                # Calculate ear line tilt angle
                # This measures how tilted the ear-to-ear line is relative to
                # what it should be if both ears were equidistant from centre
                #
                # Imagine looking down at the mouse from above:
                # - If both ears are equidistant from centre, the ear line should be
                #   perpendicular to the line from centre to the mouse
                # - If one ear is closer, the ear line tilts away from perpendicular
                # - Positive angle = clockwise tilt, negative = counter-clockwise
                
                # 1. Find midpoint between ears
                mid_x = (left_x + right_x) / 2
                mid_y = (left_y + right_y) / 2
                
                # 2. Vector from centre to midpoint (radial direction)
                radial_x = mid_x - centre_x
                radial_y = mid_y - centre_y
                
                # 3. Calculate the "ideal" ear line direction (perpendicular to radial)
                # For a perpendicular vector, swap components and negate one
                ideal_ear_vector_x = -radial_y
                ideal_ear_vector_y = radial_x
                
                # 4. Actual ear-to-ear vector (from left to right)
                actual_ear_vector_x = right_x - left_x
                actual_ear_vector_y = right_y - left_y
                
                # 5. Calculate angle between ideal and actual ear lines
                # Using dot product formula: cos(theta) = (a·b) / (|a||b|)
                dot_product = (ideal_ear_vector_x * actual_ear_vector_x + 
                              ideal_ear_vector_y * actual_ear_vector_y)
                
                ideal_magnitude = np.sqrt(ideal_ear_vector_x**2 + ideal_ear_vector_y**2)
                actual_magnitude = np.sqrt(actual_ear_vector_x**2 + actual_ear_vector_y**2)
                
                if ideal_magnitude > 0 and actual_magnitude > 0:
                    cos_angle = dot_product / (ideal_magnitude * actual_magnitude)
                    # Clamp to [-1, 1] to avoid numerical errors
                    cos_angle = np.clip(cos_angle, -1, 1)
                    tilt_angle_rad = np.arccos(cos_angle)
                    
                    # Determine sign: use cross product to check if rotation is clockwise or counter-clockwise
                    # Cross product in 2D: a×b = ax*by - ay*bx
                    cross_product = (ideal_ear_vector_x * actual_ear_vector_y - 
                                   ideal_ear_vector_y * actual_ear_vector_x)
                    
                    # Convert to degrees with appropriate sign
                    tilt_angle_deg = np.degrees(tilt_angle_rad)
                    if cross_product < 0:
                        tilt_angle_deg = -tilt_angle_deg
                    
                    # Normalise to [-90, 90] range
                    # (ears can't be tilted more than 90 degrees in either direction)
                    if tilt_angle_deg > 90:
                        tilt_angle_deg = 180 - tilt_angle_deg
                    elif tilt_angle_deg < -90:
                        tilt_angle_deg = -180 - tilt_angle_deg
                else:
                    tilt_angle_deg = 0  # Default if calculation fails
                
                # Calculate ear separation distance
                ear_separation = np.sqrt((right_x - left_x)**2 + (right_y - left_y)**2)
                
                # Store all relevant data for this trial
                trial_data = {
                    'distance_diff': distance_diff,
                    'left_distance': left_distance,
                    'right_distance': right_distance,
                    'left_ear_x': left_x,
                    'left_ear_y': left_y,
                    'right_ear_x': right_x,
                    'right_ear_y': right_y,
                    'tilt_angle': tilt_angle_deg,
                    'ear_separation': ear_separation,
                    'mouse_id': mouse_id,  # Store mouse ID for grouping
                }
                
                # Categorise trial by cue mode and store data
                correct_port = trial.get('correct_port', '')
                
                if 'all_trials' in cue_modes:
                    ear_differences_by_mode['all_trials'].append(distance_diff)
                    ear_differences_by_mouse[mouse_id]['all_trials'].append(trial_data)
                
                if 'visual_trials' in cue_modes and 'audio' not in correct_port:
                    ear_differences_by_mode['visual_trials'].append(distance_diff)
                    ear_differences_by_mouse[mouse_id]['visual_trials'].append(trial_data)
                
                if 'audio_trials' in cue_modes and 'audio' in correct_port:
                    ear_differences_by_mode['audio_trials'].append(distance_diff)
                    ear_differences_by_mouse[mouse_id]['audio_trials'].append(trial_data)
        
        # Store results for this dataset
        all_results[dataset_name] = {
            'by_mode': ear_differences_by_mode,
            'by_mouse': dict(ear_differences_by_mouse),
            'excluded': excluded,
            'session_count': session_count,
            'mouse_session_counts': dict(mouse_session_counts),
        }
    
    # Generate report
    print("="*70)
    print("EAR DISTANCE ANALYSIS REPORT")
    print("="*70)
    print(f"Analysis timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nImage dimensions used: {img_width} x {img_height} pixels")
    print(f"Image centre: ({img_width/2:.1f}, {img_height/2:.1f})")
    
    # Report for each dataset
    for dataset_name, results in all_results.items():
        print(f"\n{'='*70}")
        print(f"DATASET: {dataset_name}")
        print(f"{'='*70}")
        
        print(f"\n{'DATA COLLECTION SUMMARY':^70}")
        print("-"*70)
        print(f"Total sessions processed: {results['session_count']}")
        print(f"Total mice found: {len(results['mouse_session_counts'])}")
        print(f"Mice analysed: {', '.join([m for m in results['mouse_session_counts'].keys() if m not in exclusion_mice])}")
        if exclusion_mice:
            print(f"Mice excluded: {', '.join(exclusion_mice)}")
        
        print(f"\n{'EXCLUSION SUMMARY':^70}")
        print("-"*70)
        total_excluded = sum(results['excluded'].values())
        print(f"Total trials excluded: {total_excluded}")
        for reason, count in results['excluded'].items():
            if count > 0:
                print(f"  {reason.replace('_', ' ').title()}: {count}")
        
        print(f"\n{'RESULTS BY TRIAL TYPE':^70}")
        print("-"*70)
        
        for mode in cue_modes:
            differences = results['by_mode'][mode]
            if differences:
                mean_diff = np.mean(differences)
                std_diff = np.std(differences)
                sem_diff = std_diff / np.sqrt(len(differences))
                median_diff = np.median(differences)
                
                print(f"\n{mode.upper()}:")
                print(f"  Number of trials: {len(differences)}")
                print(f"  Mean distance difference: {mean_diff:+.2f} pixels")
                print(f"  Standard deviation: {std_diff:.2f} pixels")
                print(f"  Standard error: {sem_diff:.2f} pixels")
                print(f"  Median difference: {median_diff:+.2f} pixels")
                print(f"  Range: [{np.min(differences):.2f}, {np.max(differences):.2f}] pixels")
                
                # Interpretation
                if mean_diff > 0:
                    print(f"  → Right ear tends to be {abs(mean_diff):.2f} pixels further from centre")
                else:
                    print(f"  → Left ear tends to be {abs(mean_diff):.2f} pixels further from centre")
                
                # Distribution summary
                right_further = sum(1 for d in differences if d > 0)
                left_further = sum(1 for d in differences if d < 0)
                equal_distance = sum(1 for d in differences if d == 0)
                
                print(f"  Distribution:")
                print(f"    Right ear further: {right_further} trials ({100*right_further/len(differences):.1f}%)")
                print(f"    Left ear further: {left_further} trials ({100*left_further/len(differences):.1f}%)")
                if equal_distance > 0:
                    print(f"    Equal distance: {equal_distance} trials ({100*equal_distance/len(differences):.1f}%)")
                
                # Extract and analyse tilt angles
                all_trial_data = []
                for mouse_data in results['by_mouse'].values():
                    all_trial_data.extend(mouse_data[mode])
                
                if all_trial_data:
                    tilt_angles = [d['tilt_angle'] for d in all_trial_data]
                    mean_tilt = np.mean(tilt_angles)
                    std_tilt = np.std(tilt_angles)
                    median_tilt = np.median(tilt_angles)
                    
                    print(f"\n  Ear Line Tilt Analysis:")
                    print(f"    Mean tilt angle: {mean_tilt:+.2f}°")
                    print(f"    Standard deviation: {std_tilt:.2f}°")
                    print(f"    Median tilt: {median_tilt:+.2f}°")
                    print(f"    Range: [{np.min(tilt_angles):.2f}°, {np.max(tilt_angles):.2f}°]")
                    
                    # Interpretation
                    if mean_tilt > 0:
                        print(f"    → Ears tend to be tilted {abs(mean_tilt):.1f}° clockwise")
                    else:
                        print(f"    → Ears tend to be tilted {abs(mean_tilt):.1f}° counter-clockwise")
                    
                    # Correlation between distance difference and tilt
                    distance_diffs = [d['distance_diff'] for d in all_trial_data]
                    if len(distance_diffs) > 2:
                        correlation, p_corr = stats.pearsonr(distance_diffs, tilt_angles)
                        print(f"    Correlation with distance diff: r={correlation:.3f} (p={p_corr:.4f})")
                        
                        # Also show mean ear separation
                        ear_seps = [d['ear_separation'] for d in all_trial_data]
                        mean_sep = np.mean(ear_seps)
                        print(f"    Mean ear separation: {mean_sep:.1f} pixels")
                        
                        # Theoretical relationship
                        print(f"    Note: A {mean_diff:.1f} pixel distance difference with")
                        print(f"          {mean_sep:.1f} pixel ear separation corresponds to")
                        theoretical_angle = np.degrees(np.arcsin(abs(mean_diff)/mean_sep)) if mean_sep > abs(mean_diff) else 90.0
                        print(f"          approximately {theoretical_angle:.1f}° theoretical tilt")
            else:
                print(f"\n{mode.upper()}: No trials found")
    
    # Statistical comparisons if multiple datasets
    comparisons = {}
    if is_dict_input and len(sessions_dict) == 2:
        print(f"\n{'='*70}")
        print(f"STATISTICAL COMPARISONS")
        print(f"{'='*70}")
        
        dataset_names = list(sessions_dict.keys())
        dataset1_name = dataset_names[0]
        dataset2_name = dataset_names[1]
        
        for mode in cue_modes:
            print(f"\n{mode.upper()} - {dataset1_name} vs {dataset2_name}:")
            
            # Get data for both datasets
            data1 = all_results[dataset1_name]['by_mode'][mode]
            data2 = all_results[dataset2_name]['by_mode'][mode]
            
            if data1 and data2:
                # Basic statistics
                mean1, mean2 = np.mean(data1), np.mean(data2)
                std1, std2 = np.std(data1), np.std(data2)
                n1, n2 = len(data1), len(data2)
                
                print(f"  {dataset1_name}: n={n1}, mean={mean1:+.2f}±{std1:.2f}")
                print(f"  {dataset2_name}: n={n2}, mean={mean2:+.2f}±{std2:.2f}")
                print(f"  Mean difference: {mean2 - mean1:+.2f} pixels")
                
                # Test for normality
                if n1 >= 8 and n2 >= 8:  # Shapiro-Wilk requires at least 3 samples
                    _, p_norm1 = stats.shapiro(data1)
                    _, p_norm2 = stats.shapiro(data2)
                    both_normal = p_norm1 > 0.05 and p_norm2 > 0.05
                else:
                    both_normal = False
                
                # Choose and perform statistical test
                if statistical_test == 'auto':
                    use_ttest = both_normal
                elif statistical_test == 'ttest':
                    use_ttest = True
                else:  # mannwhitney
                    use_ttest = False
                
                if use_ttest:
                    # Independent samples t-test
                    statistic, p_value = stats.ttest_ind(data1, data2, equal_var=False)
                    test_name = "Welch's t-test"
                else:
                    # Mann-Whitney U test
                    statistic, p_value = stats.mannwhitneyu(data1, data2, alternative='two-sided')
                    test_name = "Mann-Whitney U test"
                
                # Calculate effect size (Cohen's d)
                pooled_std = np.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))
                if pooled_std > 0:
                    cohens_d = (mean2 - mean1) / pooled_std
                else:
                    cohens_d = 0
                
                # Report results
                print(f"\n  Statistical Test: {test_name}")
                print(f"  Test statistic: {statistic:.4f}")
                print(f"  p-value: {p_value:.4f}")
                print(f"  Cohen's d: {cohens_d:.3f}")
                
                # Interpretation
                if p_value < 0.001:
                    sig_text = "*** (p < 0.001)"
                elif p_value < 0.01:
                    sig_text = "** (p < 0.01)"
                elif p_value < 0.05:
                    sig_text = "* (p < 0.05)"
                else:
                    sig_text = "ns (p ≥ 0.05)"
                
                print(f"  Significance: {sig_text}")
                
                # Effect size interpretation
                abs_d = abs(cohens_d)
                if abs_d < 0.2:
                    effect_text = "negligible"
                elif abs_d < 0.5:
                    effect_text = "small"
                elif abs_d < 0.8:
                    effect_text = "medium"
                else:
                    effect_text = "large"
                
                print(f"  Effect size: {effect_text}")
                
                # Also compare tilt angles
                print(f"\n  Ear Tilt Angle Comparison:")
                
                # Extract tilt angles for both datasets
                tilts1 = []
                for mouse_data in all_results[dataset1_name]['by_mouse'].values():
                    tilts1.extend([d['tilt_angle'] for d in mouse_data[mode]])
                
                tilts2 = []
                for mouse_data in all_results[dataset2_name]['by_mouse'].values():
                    tilts2.extend([d['tilt_angle'] for d in mouse_data[mode]])
                
                if tilts1 and tilts2:
                    mean_tilt1 = np.mean(tilts1)
                    mean_tilt2 = np.mean(tilts2)
                    std_tilt1 = np.std(tilts1)
                    std_tilt2 = np.std(tilts2)
                    
                    print(f"    {dataset1_name}: mean tilt = {mean_tilt1:+.2f}°±{std_tilt1:.2f}°")
                    print(f"    {dataset2_name}: mean tilt = {mean_tilt2:+.2f}°±{std_tilt2:.2f}°")
                    print(f"    Tilt difference: {mean_tilt2 - mean_tilt1:+.2f}°")
                    
                    # Statistical test for tilt angles
                    if use_ttest:
                        tilt_stat, tilt_p = stats.ttest_ind(tilts1, tilts2, equal_var=False)
                    else:
                        tilt_stat, tilt_p = stats.mannwhitneyu(tilts1, tilts2, alternative='two-sided')
                    
                    print(f"    Tilt angle p-value: {tilt_p:.4f}")
                
                # Store comparison results
                comparisons[mode] = {
                    'dataset1': dataset1_name,
                    'dataset2': dataset2_name,
                    'n1': n1,
                    'n2': n2,
                    'mean1': mean1,
                    'mean2': mean2,
                    'std1': std1,
                    'std2': std2,
                    'mean_diff': mean2 - mean1,
                    'test_name': test_name,
                    'statistic': statistic,
                    'p_value': p_value,
                    'cohens_d': cohens_d,
                    'significant': p_value < 0.05,
                    'mean_tilt1': mean_tilt1 if 'mean_tilt1' in locals() else None,
                    'mean_tilt2': mean_tilt2 if 'mean_tilt2' in locals() else None,
                    'tilt_diff': mean_tilt2 - mean_tilt1 if 'mean_tilt1' in locals() else None,
                    'tilt_p_value': tilt_p if 'tilt_p' in locals() else None,
                }
            else:
                print(f"  Cannot compare - insufficient data in one or both datasets")
    
    # Per-mouse analysis by dataset
    if verbose:
        for dataset_name, results in all_results.items():
            print(f"\n{'='*70}")
            print(f"INDIVIDUAL MOUSE RESULTS - {dataset_name}")
            print("-"*70)
            
            for mouse_id in sorted(results['by_mouse'].keys()):
                mouse_data = results['by_mouse'][mouse_id]
                print(f"\nMouse {mouse_id} (Sessions: {results['mouse_session_counts'][mouse_id]}):")
                
                for mode in cue_modes:
                    trial_data_list = mouse_data[mode]
                    if trial_data_list:
                        differences = [d['distance_diff'] for d in trial_data_list]
                        mean_diff = np.mean(differences)
                        std_diff = np.std(differences)
                        print(f"  {mode}: n={len(differences)}, "
                              f"mean={mean_diff:+.2f}±{std_diff:.2f} pixels, "
                              f"range=[{np.min(differences):.2f}, {np.max(differences):.2f}]")
                    else:
                        print(f"  {mode}: No trials")
    
    print("\n" + "="*70)
    
    # Prepare return value based on input type
    if is_dict_input:
        return {
            'datasets': all_results,
            'comparisons': comparisons,
            'image_dimensions': (img_width, img_height),
        }
    else:
        # For single dataset input, return in original format for compatibility
        single_result = all_results['Dataset']
        return {
            'by_mode': single_result['by_mode'],
            'by_mouse': single_result['by_mouse'],
            'excluded': single_result['excluded'],
            'session_count': single_result['session_count'],
            'mouse_session_counts': single_result['mouse_session_counts'],
            'image_dimensions': (img_width, img_height),
        }
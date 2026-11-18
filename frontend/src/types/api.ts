export type UserRole = "PROFESSOR" | "ALUNO";
export type FuelType = "COAL" | "OIL" | "NUCLEAR" | "GAS" | "OTHER";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Classroom {
  id: string;
  name: string;
  description: string | null;
  invite_code: string;
  professor_id: string;
  created_at: string;
  student_count: number;
}

export interface StudentMember {
  id: string;
  email: string;
  full_name: string;
  joined_at: string;
  project_count: number;
}

export interface AuditRunSummary {
  run_id: string;
  project_id: string;
  project_name: string;
  student_id: string;
  student_name: string;
  student_email: string;
  run_type: string;
  created_at: string;
  summary: SimulationSummary;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  owner_name: string | null;
  classroom_id: string | null;
  is_template: boolean;
  created_at: string;
  updated_at: string;
}

export interface HydroPlant {
  id: string;
  project_id: string;
  name: string;
  vmax_hm3: number;
  vmin_hm3: number;
  productivity_mw_m3s: number;
  installed_power_mw: number;
  downstream_plant_id: string | null;
}

export interface REESummary {
  ea_max_total_mwm: number;
  ea_max_by_plant_mwm: Record<string, number>;
  cascades: Record<string, string[]>;
  accumulated_productivity: Record<string, number>;
}

export interface InflowPoint {
  year: number;
  month: number;
  flow_m3s: number;
  is_incremental: boolean;
}

export interface ThermalPlant {
  id: string;
  project_id: string;
  name: string;
  fuel_type: FuelType;
  installed_power_mw: number;
  fc_max: number;
  fc_min: number;
  fixed_cost_usd_kw: number;
  variable_cost_usd_mwh: number;
  useful_life_years: number;
  guide_curve: number[];
  enabled: boolean;
}

export interface SimulationConfig {
  id: string;
  project_id: string;
  load_mwm: number;
  initial_earm_pct: number;
  start_year: number;
  start_month: number;
  end_year: number;
  end_month: number;
  interest_rate_pct: number;
  gh_max_mwm: number | null;
}

export interface CriticalPeriod {
  start_year: number;
  start_month: number;
  end_year: number;
  end_month: number;
  duration_months: number;
  min_earm_mwm: number;
  min_earm_pct: number;
}

export interface ThermalEconomicItem {
  plant_id: string;
  name: string;
  fuel_type: FuelType;
  installed_power_mw: number;
  avg_generation_mwm: number;
  frc: number;
  fixed_cost_usd_year: number;
  variable_cost_usd_year: number;
  total_cost_usd_year: number;
  fixed_cost_kusd_year: number;
  variable_cost_kusd_year: number;
  total_cost_kusd_year: number;
}

export interface SimulationSummary {
  ea_max_mwm: number;
  initial_earm_mwm: number;
  critical_period: CriticalPeriod | null;
  economics: ThermalEconomicItem[];
  total_fixed_cost_usd_year: number;
  total_variable_cost_usd_year: number;
  total_cost_usd_year: number;
  total_cost_kusd_year: number;
  max_deficit_mwm: number;
  total_deficit_mwm: number;
  deficit_months: number;
  avg_ena_mwm: number;
  avg_thermal_mwm: number;
  avg_hydro_mwm: number;
  total_spilled_mwm: number;
  firm_energy_mwm?: number;
  bisection_iterations?: number;
}

export interface MonthlyResult {
  year: number;
  month: number;
  enat_mwm: number;
  total_thermal_mwm: number;
  gh_delivered_mwm: number;
  earm_mwm: number;
  earm_pct: number;
  evert_mwm: number;
  deficit_mwm: number;
  thermal_dispatch_by_plant: Record<string, number>;
}

export interface SimulationRun {
  id: string;
  project_id: string;
  run_type: string;
  config_snapshot: Omit<SimulationConfig, "id" | "project_id">;
  summary: SimulationSummary;
  created_at: string;
  monthly_results: MonthlyResult[];
}

export interface ScreeningPoint {
  hours: number;
  total_cost_usd: number;
  total_cost_kusd: number;
  unit_cost_usd_kw_year: number;
}

export interface ScreeningSeries {
  plant_id: string;
  name: string;
  fuel_type: FuelType;
  installed_power_mw: number;
  frc: number;
  fixed_cost_usd_year: number;
  variable_cost_usd_mwh: number;
  points: ScreeningPoint[];
}

export interface SensitivityResponse {
  interest_rate_pct: number;
  series: ScreeningSeries[];
}

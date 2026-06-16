export type ExamSessionStatus = 'scheduled' | 'active' | 'completed' | 'cancelled';

export interface Assignment {
  id: string;
  invigilator_id: string;
  hall_id: string;
  role: 'primary' | 'secondary';
  exam_session_id: string;
  monitoring_started_at: string | null;
  monitoring_ended_at: string | null;
  
  // Enriched fields from backend
  exam_name: string;
  hall_name: string;
  scheduled_start: string;
  scheduled_end: string;
}

export interface HallMonitoringStatus {
  hall_id: string;
  hall_name: string;
  exam_name: string;
  is_active: boolean;
  started_at: string | null;
  ended_at: string | null;
  stats: {
    student_count: number;
    active_alerts: number;
  };
  alerts: HallAlert[];
}

export interface HallAlert {
  id: string;
  event_id?: string | null;
  type: string;
  message: string;
  event_type?: string;
  severity?: string | null;
  timestamp: string | null;
  confidence_score?: number | null;
  status: 'pending' | 'claimed' | 'confirmed' | 'cancelled' | string;
  claimed_by?: string | null;
  camera_name?: string | null;
  location?: string;
  track_id?: number | null;
  looking_at?: number | null;
  has_clip: boolean;
  has_snapshot: boolean;
}

export interface DeviceReadiness {
  id: string;
  type: 'camera' | 'microphone' | string;
  identifier: string;
  name: string;
  status: 'passed' | 'failed';
  message: string;
}

export interface HallReadiness {
  session_id: string;
  hall_id: string;
  hall_name: string;
  exam_name: string;
  checked_at: string;
  overall_status: 'passed' | 'warning';
  failed_count: number;
  devices: DeviceReadiness[];
}

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
  alerts: Array<{
    type: string;
    message: string;
    timestamp: string;
  }>;
}

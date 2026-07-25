export type MatchMode = "work" | "education" | "military";

export type IntakeForm = {
  leaver_type: string;
  location: string;
  courses: string[];
  interests: string[];
  passions: string[];
  work_experience: string[];
  qualification_level: string;
  availability: string;
  psych_answers: Record<string, string>;
  use_openai_briefing: boolean;
  allow_anonymous_logging: boolean;
  mode: MatchMode;
};

export type Pathway = {
  id?: string;
  title: string;
  summary?: string;
  steps?: string[];
  local_anchors?: string[];
  sector?: string;
  reason?: string;
  chip?: string;
  tags?: string[];
  source?: string;
};

export type PersonaFit = {
  persona: string;
  cluster_id?: number | null;
  distance: number;
  closeness: number;
  is_primary: boolean;
  is_runner_up?: boolean;
};

export type PersonaMap2D = {
  you: { x: number; y: number };
  centroids: {
    persona: string;
    x: number;
    y: number;
    is_primary?: boolean;
  }[];
};

export type MatchCompany = {
  kind?: "employer" | "course" | "military";
  company_id: string;
  name: string;
  town: string;
  summary: string;
  website: string;
  provider?: string;
  service?: string;
  level?: string;
  course_type?: string;
  course_type_label?: string;
  study_mode?: string;
  region?: string;
  sector_score?: number;
  entry_score?: number;
  hiring_score?: number;
  hybrid_score?: number;
  cosine_sim?: number;
  hiring_signal?: string;
  sector_fit_label: string;
  entry_fit_label: string;
  hiring_label: string;
  overall_label: string;
  briefing_markdown?: string | null;
  briefing_source?: "openai" | null;
};

export type Microcredential = {
  cred_id: string;
  title: string;
  provider: string;
  town: string;
  region?: string;
  level?: string;
  sectors?: string;
  summary?: string;
  website?: string;
  elcas_status?: string;
  final_score?: number;
};

export type OnlineCourse = {
  course_id: string;
  title: string;
  description: string;
  provider: string;
  url: string;
  sectors?: string;
  score?: number;
};

export type MatchResponse = {
  mode?: MatchMode;
  leaver: {
    profile_text?: string;
    target_sectors?: string[];
    interest_sectors?: string[];
    persona?: string;
    cluster_id?: number | null;
    psych?: { dominant_riasec?: string[] };
  };
  pathways: Pathway[];
  training_routes?: Pathway[];
  persona?: string;
  runner_up?: string | null;
  persona_blurb?: string;
  persona_disclaimer?: string;
  persona_fit?: PersonaFit[];
  persona_map_2d?: PersonaMap2D | null;
  learning_event_id?: string | null;
  briefings_enabled?: boolean;
  matches: MatchCompany[];
  microcredentials?: Microcredential[];
  online_courses?: OnlineCourse[];
  online_courses_disclaimer?: string;
  data_note?: string;
};

export type TaxonomyResponse = {
  intake: {
    leaver_types: string[];
    locations: string[];
    interests: string[];
    passions: string[];
    work_experience_types: string[];
    qualification_levels: string[];
    availability: string[];
    course_areas: {
      school_college: string[];
      university: string[];
    };
  };
  psych: {
    disclaimer?: string;
    questions: {
      id: string;
      prompt: string;
      options: { id: string; label: string }[];
    }[];
  };
};

export interface AuthUser {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  is_subscriber: boolean;
  is_admin: boolean;
  member_since: string;  // ISO date e.g. "2025-01-14"
}

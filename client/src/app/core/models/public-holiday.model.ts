export interface PublicHoliday {
  date: string;
  localName: string;
  name: string;
  countryCode: string;
  fixed: boolean;
  global: boolean;
  counties?: string[] | null;
  launchYear?: number | null;
  types: string[];
}

export interface PublicHolidayCountry {
  countryCode: string;
  name: string;
}

export interface PublicHolidayFeedResponse {
  countryCode: string;
  enabled: boolean;
  year: number;
  holidays: PublicHoliday[];
}

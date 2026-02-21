export const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const USE_MOCK_DATA = false;

export const VALID_ZONES = [
  'B1','B2','B3','B4','B5',
  'K1','K2','K3','K4','K5','K6','K7',
  'M1','M2','M3','M4','M5','M6','M7','M8','M9',
  'Q1','Q2','Q3','Q4','Q5','Q6','Q7',
  'S1','S2','S3'
];

export const ZONE_NAMES = {
  'B1':'South Bronx', 'B2':'West/Central Bronx', 'B3':'East Bronx',
  'B4':'North Bronx', 'B5':'Riverdale',
  'K1':'Southern Brooklyn', 'K2':'Park Slope', 'K3':'Bushwick',
  'K4':'East New York', 'K5':'Bed-Stuy', 'K6':'Borough Park', 'K7':'Williamsburg',
  'M1':'Lower Manhattan', 'M2':'Midtown South', 'M3':'Midtown',
  'M4':'Murray Hill', 'M5':'Upper East Side S', 'M6':'Upper East Side N',
  'M7':'Harlem', 'M8':'Washington Heights S', 'M9':'Washington Heights N',
  'Q1':'Far Rockaway', 'Q2':'Flushing', 'Q3':'Forest Hills',
  'Q4':'Ridgewood', 'Q5':'Jamaica', 'Q6':'Astoria', 'Q7':'Whitestone',
  'S1':'North Shore SI', 'S2':'Mid-Island SI', 'S3':'South Shore SI'
};

export const ZONE_CENTROIDS = {
  'B1': [-73.9101, 40.8116], 'B2': [-73.9196, 40.8448], 'B3': [-73.8784, 40.8189],
  'B4': [-73.8600, 40.8784], 'B5': [-73.9056, 40.8651],
  'K1': [-73.9857, 40.5995], 'K2': [-73.9442, 40.6501], 'K3': [-73.9075, 40.6929],
  'K4': [-73.9015, 40.6501], 'K5': [-73.9283, 40.6801], 'K6': [-73.9645, 40.6401], 'K7': [-73.9573, 40.7201],
  'M1': [-74.0060, 40.7128], 'M2': [-74.0000, 40.7484], 'M3': [-73.9857, 40.7580],
  'M4': [-73.9784, 40.7484], 'M5': [-73.9584, 40.7701], 'M6': [-73.9484, 40.7884],
  'M7': [-73.9428, 40.8048], 'M8': [-73.9373, 40.8284], 'M9': [-73.9312, 40.8484],
  'Q1': [-73.7840, 40.6001], 'Q2': [-73.8284, 40.7501], 'Q3': [-73.8784, 40.7201],
  'Q4': [-73.9073, 40.7101], 'Q5': [-73.8073, 40.6901], 'Q6': [-73.9173, 40.7701], 'Q7': [-73.8373, 40.7701],
  'S1': [-74.1115, 40.6401], 'S2': [-74.1515, 40.5901], 'S3': [-74.1915, 40.5301]
};

export const ZONE_SVI = {
  'B1':0.94, 'B2':0.89, 'B3':0.87, 'B4':0.72, 'B5':0.68,
  'K1':0.52, 'K2':0.58, 'K3':0.82, 'K4':0.84, 'K5':0.79, 'K6':0.60, 'K7':0.45,
  'M1':0.31, 'M2':0.18, 'M3':0.15, 'M4':0.20, 'M5':0.12,
  'M6':0.14, 'M7':0.73, 'M8':0.65, 'M9':0.61,
  'Q1':0.71, 'Q2':0.44, 'Q3':0.38, 'Q4':0.55, 'Q5':0.67, 'Q6':0.48, 'Q7':0.41,
  'S1':0.38, 'S2':0.32, 'S3':0.28
};

export const ZONE_BOROUGH = {
  'B1':'BRONX','B2':'BRONX','B3':'BRONX','B4':'BRONX','B5':'BRONX',
  'K1':'BROOKLYN','K2':'BROOKLYN','K3':'BROOKLYN','K4':'BROOKLYN','K5':'BROOKLYN','K6':'BROOKLYN','K7':'BROOKLYN',
  'M1':'MANHATTAN','M2':'MANHATTAN','M3':'MANHATTAN','M4':'MANHATTAN','M5':'MANHATTAN','M6':'MANHATTAN','M7':'MANHATTAN','M8':'MANHATTAN','M9':'MANHATTAN',
  'Q1':'QUEENS','Q2':'QUEENS','Q3':'QUEENS','Q4':'QUEENS','Q5':'QUEENS','Q6':'QUEENS','Q7':'QUEENS',
  'S1':'RICHMOND / STATEN ISLAND','S2':'RICHMOND / STATEN ISLAND','S3':'RICHMOND / STATEN ISLAND'
};

export const DEMO_SCENARIOS = {
  friday_peak: { hour: 20, dow: 4, month: 10, temperature: 15, precipitation: 0, windspeed: 10, ambulances: 5 },
  monday_quiet: { hour: 4, dow: 0, month: 10, temperature: 15, precipitation: 0, windspeed: 10, ambulances: 5 },
  storm: { hour: 18, dow: 2, month: 11, temperature: 8, precipitation: 8, windspeed: 30, ambulances: 7 },
};

export const WEATHER_PRESETS = {
  none: { temperature: 15, precipitation: 0, windspeed: 10, label: 'Clear' },
  light: { temperature: 12, precipitation: 2, windspeed: 15, label: 'Light Rain' },
  heavy: { temperature: 8, precipitation: 8, windspeed: 30, label: 'Heavy Storm' },
};

export const DOW_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

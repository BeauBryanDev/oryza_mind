import type { WeatherData } from '../types';
import { api } from './api';

const DEMO_WEATHER: WeatherData = {
  city: 'Bogota , Colombia',
  temperatureC: 28,  // stub placeholder,  it is not a demo
  humidityPct: 78,  // v2 wI will use a real API in backend endpoint
  rainPct: 0,  // show weather is  good but not a critical feature yet 
  condition: 'smooth rains',
};

export async function fetchWeather(): Promise<WeatherData> {
  //
  try {
    const { data } = await api.get<WeatherData>('/weather');
    return data;
  } catch {
    await new Promise((r) => setTimeout(r, 300));
    return DEMO_WEATHER;
  }
}

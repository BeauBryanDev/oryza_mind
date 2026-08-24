import { useEffect, useState } from 'react';
import type { WeatherData } from '../types';
import { fetchWeather } from '../services/weatherService';

export function useWeather() {

  const [data, setData] = useState<WeatherData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {

    let alive = true;
    fetchWeather()

      .then((d) => { if (alive) setData(d); })
      .finally(() => { if (alive) setLoading(false); });

    return () => { alive = false; };
    
  }, []);

  return { data, loading };
}

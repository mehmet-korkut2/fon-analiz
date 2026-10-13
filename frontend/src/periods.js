// Grafik dönemleri: [anahtar, kısa ad, uzun ad, API parametresi].
// YBB'nin parametresi yıla bağlı olduğundan null; ayrıca hesaplanır.
export const PERIODS = [
  ['1A', '1A', '1 ay', { months: 1 }],
  ['3A', '3A', '3 ay', { months: 3 }],
  ['6A', '6A', '6 ay', { months: 6 }],
  ['YBB', 'YBB', 'Yılbaşından bu yana', null],
  ['1Y', '1Y', '1 yıl', { months: 12 }],
  ['3Y', '3Y', '3 yıl', { months: 36 }],
  ['5Y', '5Y', '5 yıl', { months: 60 }],
]

export const DEFAULT_PERIOD = '1Y'

export const findPeriod = (key) => PERIODS.find(([k]) => k === key) || PERIODS.find(([k]) => k === DEFAULT_PERIOD)

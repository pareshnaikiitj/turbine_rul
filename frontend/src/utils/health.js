export function healthTone(score) {
  if (score >= 70) return 'tone-healthy';
  if (score >= 40) return 'tone-watch';
  return 'tone-critical';
}

export function ipKey(ip) {
  if (!ip) return [999, 999, 999, 999];
  return ip.split('.').map((n) => parseInt(n, 10) || 0);
}

export function compareIp(a, b) {
  const ka = ipKey(a), kb = ipKey(b);
  for (let i = 0; i < 4; i++) if (ka[i] !== kb[i]) return ka[i] - kb[i];
  return 0;
}

export function deviceLabel(d) {
  return d.name || d.hostname || d.vendor || 'Unnamed device';
}

export function deviceSubtitle(d) {
  const parts = [];
  if (d.name && d.hostname) parts.push(d.hostname);
  if (d.vendor && (d.name || d.hostname)) parts.push(d.vendor);
  return parts.join(' / ');
}

export function timeAgo(iso, now = Date.now()) {
  if (!iso) return 'never';
  const s = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d} d ago`;
  return new Date(iso).toLocaleDateString();
}

export function formatDateTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

export function formatTime(iso) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

export function dayLabel(iso) {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });
}

export const TYPE_LABELS = {
  '': 'Not set', router: 'Router', computer: 'Computer', laptop: 'Laptop', phone: 'Phone',
  tablet: 'Tablet', tv: 'TV', speaker: 'Speaker', camera: 'Camera', iot: 'Smart home',
  printer: 'Printer', console: 'Game console', server: 'Server', nas: 'Storage', other: 'Other',
};

export function guessType(d) {
  if (d.device_type) return d.device_type;
  const v = `${d.vendor} ${d.hostname}`.toLowerCase();
  if (d.ip && d.ip.endsWith('.1')) return 'router';
  if (/iphone|android|pixel|oneplus|xiaomi|samsung.*phone/.test(v)) return 'phone';
  if (/ipad|tablet/.test(v)) return 'tablet';
  if (/sonos|echo|homepod|bose/.test(v)) return 'speaker';
  if (/philips|hue|shelly|tuya|espressif|tasmota|sonoff|nest|ring|aqara|ikea/.test(v)) return 'iot';
  if (/samsung|lg electronics|sony|roku|chromecast|apple tv|fire tv|vizio/.test(v)) return 'tv';
  if (/hikvision|dahua|reolink|axis|ubiquiti.*cam|wyze|arlo/.test(v)) return 'camera';
  if (/synology|qnap|western digital|nas/.test(v)) return 'nas';
  if (/printer|brother|epson|canon|hp inc|hewlett/.test(v)) return 'printer';
  if (/raspberry|server|proxmox|dell|supermicro/.test(v)) return 'server';
  if (/nintendo|playstation|xbox|sony interactive/.test(v)) return 'console';
  if (/apple|macbook|intel|asus|lenovo|msi|acer|gigabyte/.test(v)) return 'computer';
  if (/ubiquiti|tp-link|netgear|asustek|mikrotik|cisco|fritz|avm|zyxel|d-link/.test(v)) return 'router';
  return '';
}

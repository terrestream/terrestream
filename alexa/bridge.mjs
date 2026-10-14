// Launch the dedicated, version-checked Alexa companion. Never reset Matter identity.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { parseArgs } from 'node:util';

const root = path.dirname(fileURLToPath(import.meta.url));
const hash = data => createHash('sha256').update(data).digest('hex');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const fail = message => { throw new Error(message); };
function write(file, value) {
  const temporary = file + '.tmp';
  fs.writeFileSync(temporary, JSON.stringify(value, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
  fs.renameSync(temporary, file);
  fs.chmodSync(file, 0o600);
}

export function check(home) {
  const record = read(path.join(home, 'terrestream-alexa.json'));
  const plugin = path.join(root, 'node_modules/matterbridge-hass');
  const upstream = read(path.join(root, 'upstream.json'));
  if (record.schema !== 1 || record.package !== plugin) fail('Companion location changed; restore the original folder.');
  if (read(path.join(plugin, 'package.json')).version !== upstream['matterbridge-hass'] ||
      read(path.join(root, 'node_modules/matterbridge/package.json')).version !== upstream.matterbridge) fail('Pinned bridge versions changed.');
  const expected = record.voc_enabled ? record.module_sha256 : record.original_sha256;
  if (hash(fs.readFileSync(path.join(plugin, 'dist/module.js'))) !== expected) fail('Plugin changed or npm replaced the VOC adapter; do not start until repaired.');
  if (record.voc_enabled && (hash(fs.readFileSync(path.join(plugin, 'dist/terrestream-alexa-voc.mjs'))) !== record.adapter_sha256 ||
      hash(fs.readFileSync(path.join(root, 'alexa_voc_adapter.mjs'))) !== record.adapter_sha256)) fail('VOC adapter changed.');
  const config = read(path.join(home, '.matterbridge/matterbridge-hass.config.json'));
  if (config.controllerStrategy !== 'Merge' || JSON.stringify(config.whiteList) !== JSON.stringify([record.device_id]) ||
      JSON.stringify(config.entityWhiteList) !== '["sensor"]' || config.splitEntities.length || config.unregisterOnShutdown ||
      config.blackList.includes('Terrestream') || config.blackList.includes(record.device_id)) fail('Dedicated single-sensor bridge selection changed.');
  const blocked = config.deviceEntityBlackList?.Terrestream ?? [];
  if (record.voc_enabled ? (!blocked.includes(record.source) || blocked.includes(record.helper)) :
      (blocked.includes(record.source) || !blocked.includes(record.helper))) fail('VOC must have exactly one selected writer.');
  return { record, config, plugin };
}

function running(pidFile) {
  if (!fs.existsSync(pidFile)) return false;
  const pid = Number(fs.readFileSync(pidFile, 'utf8'));
  if (!Number.isInteger(pid) || pid < 1) fail('Invalid companion PID file.');
  try { process.kill(pid, 0); return true; } catch (error) { if (error.code === 'ESRCH') return false; throw error; }
}

async function main() {
  const { values, positionals } = parseArgs({ allowPositionals: true, options: {
    home: { type: 'string', default: path.join(os.homedir(), '.terrestream-alexa') },
    interface: { type: 'string' }, 'frontend-port': { type: 'string', default: '8287' },
  } });
  const action = positionals[0] ?? 'check';
  if (!['check', 'register', 'start', 'restore-voc'].includes(action) || positionals.length > 1) fail('Use check, register, start, or restore-voc.');
  const home = path.resolve(values.home);
  const { record, config, plugin } = check(home);
  if (action === 'check') { console.log('Pinned bridge, adapter and single-sensor selection verified.'); return; }
  const pidFile = path.join(home, 'companion.pid');
  if (running(pidFile)) fail('The companion is running; stop it with Ctrl-C or its service manager first.');
  if (action === 'restore-voc') {
    if (!record.voc_enabled) { console.log('Canonical TVOC is already restored.'); return; }
    const original = fs.readFileSync(path.join(home, 'original-module.js'));
    if (hash(original) !== record.original_sha256) fail('Original plugin backup changed.');
    const blocked = config.deviceEntityBlackList.Terrestream;
    config.deviceEntityBlackList.Terrestream = blocked.filter(id => id !== record.source).concat(record.helper);
    fs.writeFileSync(path.join(plugin, 'dist/module.js'), original);
    fs.unlinkSync(path.join(plugin, 'dist/terrestream-alexa-voc.mjs'));
    write(path.join(home, '.matterbridge/matterbridge-hass.config.json'), config);
    record.voc_enabled = false;
    write(path.join(home, 'terrestream-alexa.json'), record);
    console.log('Canonical TVOC restored. Alexa may again label the concentration as an index; HA helpers and pairing were retained.');
    return;
  }
  const args = [path.join(root, 'node_modules/matterbridge/bin/matterbridge.js'), '--homedir', home];
  const frontendPort = Number(values['frontend-port']);
  if (!Number.isInteger(frontendPort) || frontendPort < 1024 || frontendPort > 65535) fail('Invalid frontend port.');
  if (action === 'register') args.push('--add', plugin);
  else {
    args.push('--bridge', '--frontend', String(frontendPort), '--bind', '127.0.0.1', '--port', '5540', '--novirtual', '--no-ansi');
    if (values.interface) args.push('--mdnsinterface', values.interface);
  }
  const env = { ...process.env, MATTERBRIDGE_LINK_LOCAL_PLUGINS: 'false', npm_config_prefix: root };
  delete env.TERRESTREAM_ALEXA_VOC_COMPAT;
  if (record.voc_enabled) env.TERRESTREAM_ALEXA_VOC_COMPAT = '1';
  const child = spawn(process.execPath, args, { stdio: 'inherit', env });
  fs.writeFileSync(pidFile, String(process.pid), { mode: 0o600 });
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
  child.on('error', () => { fs.rmSync(pidFile, { force: true }); console.error('Could not start Matterbridge.'); process.exitCode = 1; });
  child.on('exit', (code, signal) => { fs.rmSync(pidFile, { force: true }); process.exitCode = code ?? (signal === 'SIGINT' || signal === 'SIGTERM' ? 0 : 1); });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}

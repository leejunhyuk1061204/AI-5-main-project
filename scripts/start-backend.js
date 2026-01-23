const { spawn } = require('child_process');
const path = require('path');
const os = require('os');

const isWindows = os.platform() === 'win32';
const backendDir = path.join(__dirname, '..', 'backend');

const cmd = isWindows ? 'gradlew.bat' : './gradlew';
const args = ['clean', 'build', 'bootRun'];

console.log(`Starting Backend in ${backendDir}...`);
console.log(`Command: ${cmd} ${args.join(' ')}`);

const child = spawn(cmd, args, {
    cwd: backendDir,
    stdio: 'inherit',
    shell: isWindows
});

child.on('error', (err) => {
    console.error('Failed to start backend process:', err);
    process.exit(1);
});

child.on('exit', (code) => {
    process.exit(code);
});

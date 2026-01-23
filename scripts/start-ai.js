const { spawn } = require('child_process');
const path = require('path');
const os = require('os');

const isWindows = os.platform() === 'win32';
const rootDir = path.join(__dirname, '..');

// Python path
const pythonPath = isWindows
    ? path.join(rootDir, 'ai_env', 'Scripts', 'python.exe')
    : path.join(rootDir, 'ai_env', 'bin', 'python');

const args = [
    '-m', 'uvicorn',
    'app.main:app',
    '--app-dir', 'ai',
    '--host', '0.0.0.0',
    '--port', '8000',
    '--reload'
];

console.log(`Starting AI Server from ${rootDir}...`);
console.log(`Python: ${pythonPath}`);
console.log(`Command: python ${args.join(' ')}`);

// On Windows, we might need to verify if python exists or handle path separators carefully,
// but path.join usually handles separators.
// Executing the python executable directly.

const child = spawn(pythonPath, args, {
    cwd: rootDir,
    stdio: 'inherit',
    shell: false // Executing executable directly usually doesn't need shell=true unless using built-ins
});

child.on('error', (err) => {
    console.error('Failed to start AI process:', err);
    console.error('Check if virtual environment exists at:', pythonPath);
    process.exit(1);
});

child.on('exit', (code) => {
    process.exit(code);
});

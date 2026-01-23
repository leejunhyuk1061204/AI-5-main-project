const { spawn } = require('child_process');
const path = require('path');
const os = require('os');

const task = process.argv[2];
const isWin = os.platform() === 'win32';

if (task === 'backend') {
    const cwd = path.join(__dirname, '..', 'backend');
    const cmd = isWin ? 'gradlew' : './gradlew';
    const args = ['clean', 'build', 'bootRun'];

    console.log(`[Runner] Starting Backend in ${cwd} using ${cmd}`);

    const child = spawn(cmd, args, { cwd, stdio: 'inherit', shell: true });
    child.on('exit', code => process.exit(code));
} else if (task === 'ai') {
    const venvDir = 'ai_env';
    // Windows uses 'Scripts', Unix uses 'bin'
    const pythonExec = isWin ? path.join(venvDir, 'Scripts', 'python') : path.join(venvDir, 'bin', 'python');

    const args = ['-m', 'uvicorn', 'app.main:app', '--app-dir', 'ai', '--host', '0.0.0.0', '--port', '8000', '--reload'];

    console.log(`[Runner] Starting AI using ${pythonExec}`);

    const child = spawn(pythonExec, args, { stdio: 'inherit', shell: true });
    child.on('exit', code => process.exit(code));
} else {
    console.error("Unknown task. Use 'backend' or 'ai'");
    process.exit(1);
}

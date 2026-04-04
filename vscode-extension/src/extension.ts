/**
 * HybX Development System — VSCode Extension v0.1.7
 * Hybrid RobotiX
 *
 * Uses the ssh2 Node.js library for direct SSH connection with password auth.
 * No system ssh binary, no SSH_ASKPASS, no config file setup required.
 * Password stored securely in VSCode secret storage.
 */

import * as vscode from 'vscode';
import { Client, ClientChannel } from 'ssh2';

let outputChannel: vscode.OutputChannel;
let statusBarItem: vscode.StatusBarItem;
let logsClient: Client | null = null;
let logsChannel: ClientChannel | null = null;
let currentApp: string | null = null;
let appRunning: boolean = false;
let secretStorage: vscode.SecretStorage;

const PASSWORD_KEY = 'hybxDev.sshPassword';

export function activate(context: vscode.ExtensionContext) {
    secretStorage = context.secrets;

    outputChannel = vscode.window.createOutputChannel('HybX');
    outputChannel.show(true);
    outputChannel.appendLine('HybX Development System v0.1.7 ready.');

    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.command = 'hybxDev.start';
    updateStatusBar();
    statusBarItem.show();

    const commands: [string, () => void | Promise<void>][] = [
        ['hybxDev.connect',       cmdConnect],
        ['hybxDev.start',         cmdStart],
        ['hybxDev.stop',          cmdStop],
        ['hybxDev.restart',       cmdRestart],
        ['hybxDev.logs',          cmdLogs],
        ['hybxDev.build',         cmdBuild],
        ['hybxDev.addlib',        cmdAddlib],
        ['hybxDev.listApps',      cmdListApps],
        ['hybxDev.clean',         cmdClean],
        ['hybxDev.newrepo',       cmdNewrepo],
        ['hybxDev.clearPassword', cmdClearPassword],
    ];

    for (const [id, handler] of commands) {
        context.subscriptions.push(vscode.commands.registerCommand(id, handler));
    }

    context.subscriptions.push(statusBarItem);
    context.subscriptions.push(outputChannel);
}

export function deactivate() {
    stopLogs();
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

function cfg(): vscode.WorkspaceConfiguration {
    return vscode.workspace.getConfiguration('hybxDev');
}
function sshHost(): string {
    const host = cfg().get<string>('sshHost', 'arduino@unoq.local');
    const parts = host.split('@');
    return parts.length === 2 ? parts[1] : host;
}
function sshUser(): string {
    const host = cfg().get<string>('sshHost', 'arduino@unoq.local');
    const parts = host.split('@');
    return parts.length === 2 ? parts[0] : 'arduino';
}
function appsPath(): string { return cfg().get<string>('appsPath', '~/Arduino'); }

// ---------------------------------------------------------------------------
// Password management
// ---------------------------------------------------------------------------

async function getPassword(): Promise<string | undefined> {
    let password = await secretStorage.get(PASSWORD_KEY);
    if (!password) {
        password = await vscode.window.showInputBox({
            prompt: `SSH password for ${sshUser()}@${sshHost()}`,
            password: true,
            placeHolder: 'Enter SSH password',
            title: 'HybX: SSH Password',
            ignoreFocusOut: true
        });
        if (password) {
            await secretStorage.store(PASSWORD_KEY, password);
            outputChannel.appendLine('Password saved to secure storage.');
        }
    }
    return password;
}

async function cmdClearPassword() {
    await secretStorage.delete(PASSWORD_KEY);
    vscode.window.showInformationMessage('SSH password cleared — you will be prompted on next connect.');
}

// ---------------------------------------------------------------------------
// SSH execution via ssh2
// ---------------------------------------------------------------------------

function sshExec(cmd: string, password: string): Promise<void> {
    return new Promise((resolve, reject) => {
        const conn = new Client();

        conn.on('ready', () => {
            conn.exec(cmd, (err, stream) => {
                if (err) { conn.end(); reject(err); return; }

                stream.on('data', (data: Buffer) => {
                    outputChannel.append(data.toString());
                });
                stream.stderr.on('data', (data: Buffer) => {
                    outputChannel.append(data.toString());
                });
                stream.on('close', (code: number) => {
                    conn.end();
                    if (code === 0) { resolve(); }
                    else { reject(new Error(`Exited with code ${code}`)); }
                });
            });
        });

        conn.on('error', (err) => {
            outputChannel.appendLine(`Connection error: ${err.message}`);
            // If auth failed, clear stored password
            if (err.message.toLowerCase().includes('auth') ||
                err.message.toLowerCase().includes('handshake')) {
                secretStorage.delete(PASSWORD_KEY);
                outputChannel.appendLine('Authentication failed — password cleared. Try again.');
            }
            reject(err);
        });

        conn.connect({
            host: sshHost(),
            port: 22,
            username: sshUser(),
            password: password,
            readyTimeout: 10000,
        });
    });
}

function sshStream(cmd: string, password: string): Client {
    const conn = new Client();

    conn.on('ready', () => {
        conn.exec(cmd, (err, stream) => {
            if (err) {
                outputChannel.appendLine(`Stream error: ${err.message}`);
                conn.end();
                return;
            }
            stream.on('data', (data: Buffer) => {
                outputChannel.append(data.toString());
            });
            stream.stderr.on('data', (data: Buffer) => {
                outputChannel.append(data.toString());
            });
            stream.on('close', () => {
                outputChannel.appendLine('\n[logs ended]');
                conn.end();
            });
        });
    });

    conn.on('error', (err) => {
        outputChannel.appendLine(`Connection error: ${err.message}`);
    });

    conn.connect({
        host: sshHost(),
        port: 22,
        username: sshUser(),
        password: password,
        readyTimeout: 10000,
    });

    return conn;
}

async function runCmd(remoteCmd: string, label: string): Promise<void> {
    outputChannel.show(true);
    outputChannel.appendLine(`\n─── ${label} ───────────────────────────`);
    const password = await getPassword();
    if (!password) { throw new Error('No password provided'); }
    return sshExec(remoteCmd, password);
}

async function startLogsStream(app: string): Promise<void> {
    stopLogs();
    outputChannel.show(true);
    outputChannel.appendLine(`\n─── logs ${app} ───────────────────────────`);
    const password = await getPassword();
    if (!password) { return; }
    logsClient = sshStream(`logs ${app}`, password);
}

// ---------------------------------------------------------------------------
// Status bar
// ---------------------------------------------------------------------------

function updateStatusBar() {
    if (currentApp && appRunning) {
        statusBarItem.text = `$(play) HybX: ${currentApp}`;
        statusBarItem.tooltip = 'HybX app running — click to start/pick app';
        statusBarItem.backgroundColor = undefined;
    } else if (currentApp && !appRunning) {
        statusBarItem.text = `$(debug-stop) HybX: ${currentApp} (stopped)`;
        statusBarItem.tooltip = 'HybX app stopped — click to start';
        statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
    } else {
        statusBarItem.text = `$(circuit-board) HybX`;
        statusBarItem.tooltip = 'HybX Development System — click to start an app';
        statusBarItem.backgroundColor = undefined;
    }
}

// ---------------------------------------------------------------------------
// App picker
// ---------------------------------------------------------------------------

async function pickApp(): Promise<string | undefined> {
    const password = await getPassword();
    if (!password) { return undefined; }

    const apps = await new Promise<string[]>((resolve) => {
        const conn = new Client();
        conn.on('ready', () => {
            conn.exec(`ls -1 ${appsPath()} 2>/dev/null`, (err, stream) => {
                if (err) { conn.end(); resolve([]); return; }
                let stdout = '';
                stream.on('data', (d: Buffer) => { stdout += d.toString(); });
                stream.on('close', () => {
                    conn.end();
                    resolve(stdout.trim().split('\n').filter(Boolean));
                });
            });
        });
        conn.on('error', () => resolve([]));
        conn.connect({ host: sshHost(), port: 22, username: sshUser(), password, readyTimeout: 10000 });
    });

    const items = [...apps, '$(edit) Enter app name manually...'];

    const sel = await vscode.window.showQuickPick(items, {
        placeHolder: 'Select an app or enter manually',
        title: 'HybX: Pick App'
    });

    if (!sel) { return undefined; }
    if (sel.startsWith('$(edit)')) {
        return vscode.window.showInputBox({
            prompt: 'App name (e.g. matrix-bno)',
            placeHolder: 'matrix-bno'
        });
    }
    return sel;
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

async function cmdConnect() {
    outputChannel.show(true);
    outputChannel.appendLine(`\n─── connect ────────────────────────────`);
    outputChannel.appendLine(`Host: ${sshUser()}@${sshHost()}`);
    try {
        await runCmd('echo "HybX connected — $(uname -r)"', 'connect');
        vscode.window.showInformationMessage(`✓ Connected to ${sshHost()}`);
    } catch (err: any) {
        vscode.window.showErrorMessage(
            `Cannot connect to ${sshHost()}: ${err.message}. Use "HybX: Clear Stored SSH Password" to re-enter your password.`
        );
    }
}

async function cmdStart() {
    const app = await pickApp();
    if (!app) { return; }
    stopLogs();
    currentApp = app; appRunning = false; updateStatusBar();
    try {
        await runCmd(`start ${app}`, `start ${app}`);
        appRunning = true; updateStatusBar();
        await startLogsStream(app);
    } catch {
        vscode.window.showErrorMessage(`start ${app} failed.`);
        updateStatusBar();
    }
}

async function cmdStop() {
    stopLogs();
    const app = currentApp || await pickApp();
    if (!app) { return; }
    try {
        await runCmd(`stop ${app}`, `stop ${app}`);
        appRunning = false; updateStatusBar();
    } catch { vscode.window.showErrorMessage('stop failed.'); }
}

async function cmdRestart() {
    const app = currentApp || await pickApp();
    if (!app) { return; }
    stopLogs();
    currentApp = app; appRunning = false; updateStatusBar();
    try {
        await runCmd(`restart ${app}`, `restart ${app}`);
        appRunning = true; updateStatusBar();
        await startLogsStream(app);
    } catch {
        vscode.window.showErrorMessage(`restart ${app} failed.`);
        updateStatusBar();
    }
}

async function cmdLogs() {
    if (!currentApp) {
        vscode.window.showWarningMessage('No app running. Use HybX: Start App first.');
        return;
    }
    await startLogsStream(currentApp);
}

async function cmdBuild() {
    const sketch = await vscode.window.showInputBox({
        prompt: 'Sketch path on board (e.g. ~/Arduino/matrix-bno/sketch)',
        placeHolder: '~/Arduino/matrix-bno/sketch',
        value: currentApp ? `${appsPath()}/${currentApp}/sketch` : ''
    });
    if (!sketch) { return; }
    try {
        await runCmd(`build ${sketch}`, `build ${sketch}`);
        vscode.window.showInformationMessage(`✓ Build complete: ${sketch}`);
    } catch { vscode.window.showErrorMessage('Build failed.'); }
}

async function cmdAddlib() {
    const action = await vscode.window.showQuickPick(
        ['search', 'install', 'list', 'upgrade'],
        { placeHolder: 'addlib action', title: 'HybX: Add Library' }
    );
    if (!action) { return; }
    if (action === 'list' || action === 'upgrade') {
        await runCmd(`addlib ${action}`, `addlib ${action}`);
        return;
    }
    const libName = await vscode.window.showInputBox({
        prompt: `Library name to ${action}`,
        placeHolder: 'Adafruit SCD30'
    });
    if (!libName) { return; }
    await runCmd(`addlib ${action} "${libName}"`, `addlib ${action} ${libName}`);
}

async function cmdListApps() { await runCmd('list', 'list apps'); }

async function cmdClean() {
    const app = currentApp || await pickApp();
    if (!app) { return; }
    stopLogs();
    const confirm = await vscode.window.showWarningMessage(
        `Clean will nuke Docker + cache for "${app}" and restart. Continue?`,
        'Yes', 'No'
    );
    if (confirm !== 'Yes') { return; }
    try {
        await runCmd(`clean ${app}`, `clean ${app}`);
        appRunning = true; updateStatusBar();
        await startLogsStream(app);
    } catch { vscode.window.showErrorMessage('clean failed.'); }
}

async function cmdNewrepo() {
    const confirm = await vscode.window.showWarningMessage(
        'newrepo will wipe ~/Arduino and ~/bin on the board and re-clone from GitHub. Continue?',
        'Yes', 'No'
    );
    if (confirm !== 'Yes') { return; }
    stopLogs();
    currentApp = null; appRunning = false; updateStatusBar();
    try {
        await runCmd('newrepo', 'newrepo bootstrap');
        vscode.window.showInformationMessage('✓ newrepo complete — board environment rebuilt.');
    } catch { vscode.window.showErrorMessage('newrepo failed.'); }
}

function stopLogs() {
    if (logsClient) { logsClient.end(); logsClient = null; }
    logsChannel = null;
}

/**
 * HybX Development System — VSCode Extension v0.2.0
 * Hybrid RobotiX — Dale Weber <hybotix@hybridrobotix.io>
 *
 * Uses the ssh2 Node.js library for direct SSH connection with password auth.
 * No system ssh binary, no SSH_ASKPASS, no config file setup required.
 * Password stored securely in VSCode secret storage.
 *
 * v2.0 changes:
 *   - logs → mon
 *   - addlib → libs
 *   - newrepo → update
 *   - build takes app name not sketch path
 *   - clean is the primary build+flash+start workflow
 *   - start just starts the container (no compile)
 *   - update added as explicit command
 *   - mon streams after clean/start/restart
 */

import * as vscode from 'vscode';
import { Client, ClientChannel } from 'ssh2';

let outputChannel: vscode.OutputChannel;
let statusBarItem: vscode.StatusBarItem;
let monClient: Client | null = null;
let monChannel: ClientChannel | null = null;
let currentApp: string | null = null;
let appRunning: boolean = false;
let secretStorage: vscode.SecretStorage;

const PASSWORD_KEY = 'hybxDev.sshPassword';

export function activate(context: vscode.ExtensionContext) {
    secretStorage = context.secrets;

    outputChannel = vscode.window.createOutputChannel('HybX');
    outputChannel.show(true);
    outputChannel.appendLine('HybX Development System v0.2.0 ready.');

    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.command = 'hybxDev.clean';
    updateStatusBar();
    statusBarItem.show();

    const commands: [string, () => void | Promise<void>][] = [
        ['hybxDev.connect',       cmdConnect],
        ['hybxDev.start',         cmdStart],
        ['hybxDev.stop',          cmdStop],
        ['hybxDev.restart',       cmdRestart],
        ['hybxDev.mon',           cmdMon],
        ['hybxDev.build',         cmdBuild],
        ['hybxDev.libs',          cmdLibs],
        ['hybxDev.listApps',      cmdListApps],
        ['hybxDev.clean',         cmdClean],
        ['hybxDev.update',        cmdUpdate],
        ['hybxDev.clearPassword', cmdClearPassword],
    ];

    for (const [id, handler] of commands) {
        context.subscriptions.push(vscode.commands.registerCommand(id, handler));
    }

    context.subscriptions.push(statusBarItem);
    context.subscriptions.push(outputChannel);
}

export function deactivate() {
    stopMon();
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

function cfg(): vscode.WorkspaceConfiguration {
    return vscode.workspace.getConfiguration('hybxDev');
}
function sshHost(): string {
    const host = cfg().get<string>('sshHost', 'arduino@uno-q.local');
    const parts = host.split('@');
    return parts.length === 2 ? parts[1] : host;
}
function sshUser(): string {
    const host = cfg().get<string>('sshHost', 'arduino@uno-q.local');
    const parts = host.split('@');
    return parts.length === 2 ? parts[0] : 'arduino';
}
function appsPath(): string { return cfg().get<string>('appsPath', '~/Arduino/UNO-Q'); }

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
            // Wrap in bash login shell so ~/.bashrc is sourced and HybX PATH is set
            conn.exec(`bash -lc '${cmd.replace(/'/g, "'\\''")}'`, (err, stream) => {
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
        // Wrap in bash login shell so ~/.bashrc is sourced and HybX PATH is set
        conn.exec(`bash -lc '${cmd.replace(/'/g, "'\\''")}'`, (err, stream) => {
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
                outputChannel.appendLine('\n[mon ended]');
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

async function startMonStream(app: string): Promise<void> {
    stopMon();
    outputChannel.show(true);
    outputChannel.appendLine(`\n─── mon ${app} ───────────────────────────`);
    const password = await getPassword();
    if (!password) { return; }
    monClient = sshStream(`mon ${app}`, password);
}

// ---------------------------------------------------------------------------
// Status bar
// ---------------------------------------------------------------------------

function updateStatusBar() {
    if (currentApp && appRunning) {
        statusBarItem.text = `$(play) HybX: ${currentApp}`;
        statusBarItem.tooltip = 'HybX app running — click to clean+rebuild';
        statusBarItem.backgroundColor = undefined;
    } else if (currentApp && !appRunning) {
        statusBarItem.text = `$(debug-stop) HybX: ${currentApp} (stopped)`;
        statusBarItem.tooltip = 'HybX app stopped — click to clean+rebuild';
        statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
    } else {
        statusBarItem.text = `$(circuit-board) HybX`;
        statusBarItem.tooltip = 'HybX Development System — click to clean an app';
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
            conn.exec(`bash -lc 'ls -1 ${appsPath()} 2>/dev/null'`, (err, stream) => {
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
            prompt: 'App name (e.g. monitor-vl53l5cx)',
            placeHolder: 'monitor-vl53l5cx'
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
            `Cannot connect to ${sshHost()}: ${err.message}. Use "HybX: Clear Stored SSH Password" to re-enter.`
        );
    }
}

async function cmdClean() {
    const app = currentApp || await pickApp();
    if (!app) { return; }
    stopMon();
    currentApp = app; appRunning = false; updateStatusBar();
    const confirm = await vscode.window.showWarningMessage(
        `Clean will stop, recompile, reflash, and restart "${app}". Continue?`,
        'Yes', 'No'
    );
    if (confirm !== 'Yes') { return; }
    try {
        await runCmd(`clean ${app}`, `clean ${app}`);
        appRunning = true; updateStatusBar();
        await startMonStream(app);
    } catch {
        vscode.window.showErrorMessage(`clean ${app} failed.`);
        updateStatusBar();
    }
}

async function cmdStart() {
    const app = await pickApp();
    if (!app) { return; }
    stopMon();
    currentApp = app; appRunning = false; updateStatusBar();
    try {
        await runCmd(`start ${app}`, `start ${app}`);
        appRunning = true; updateStatusBar();
        await startMonStream(app);
    } catch {
        vscode.window.showErrorMessage(`start ${app} failed.`);
        updateStatusBar();
    }
}

async function cmdStop() {
    stopMon();
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
    stopMon();
    currentApp = app; appRunning = false; updateStatusBar();
    try {
        await runCmd(`restart ${app}`, `restart ${app}`);
        appRunning = true; updateStatusBar();
        await startMonStream(app);
    } catch {
        vscode.window.showErrorMessage(`restart ${app} failed.`);
        updateStatusBar();
    }
}

async function cmdMon() {
    const app = currentApp || await pickApp();
    if (!app) { return; }
    currentApp = app;
    await startMonStream(app);
}

async function cmdBuild() {
    const app = currentApp || await pickApp();
    if (!app) { return; }
    try {
        await runCmd(`build ${app}`, `build ${app}`);
        vscode.window.showInformationMessage(`✓ Build complete: ${app}`);
    } catch { vscode.window.showErrorMessage(`build ${app} failed.`); }
}

async function cmdLibs() {
    const action = await vscode.window.showQuickPick(
        ['list', 'install', 'search', 'upgrade', 'sync'],
        { placeHolder: 'libs action', title: 'HybX: Library Manager' }
    );
    if (!action) { return; }
    if (action === 'list' || action === 'upgrade' || action === 'sync') {
        await runCmd(`libs ${action}`, `libs ${action}`);
        return;
    }
    const libName = await vscode.window.showInputBox({
        prompt: `Library name to ${action}`,
        placeHolder: 'Adafruit SCD30'
    });
    if (!libName) { return; }
    await runCmd(`libs ${action} "${libName}"`, `libs ${action} ${libName}`);
}

async function cmdListApps() { await runCmd('list', 'list apps'); }

async function cmdUpdate() {
    stopMon();
    try {
        await runCmd('update', 'update');
        vscode.window.showInformationMessage('✓ HybX update complete.');
    } catch { vscode.window.showErrorMessage('update failed.'); }
}

function stopMon() {
    if (monClient) { monClient.end(); monClient = null; }
    monChannel = null;
}

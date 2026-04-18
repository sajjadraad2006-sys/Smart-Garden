/**
 * AgriMaster Pro — WebSocket Bridge (Optional Node.js fallback)
 * Proxies WebSocket connections for environments where direct WS isn't available.
 */
const WebSocket = require('ws');
const http = require('http');

const BACKEND_WS = 'ws://localhost:8000/ws/live';
const PORT = 8080;

const server = http.createServer((req, res) => {
    res.writeHead(200, {'Content-Type': 'text/plain'});
    res.end('AgriMaster WS Bridge running');
});

const wss = new WebSocket.Server({ server });

wss.on('connection', (clientWs) => {
    console.log('[Bridge] Client connected');
    const backendWs = new WebSocket(BACKEND_WS);

    backendWs.on('message', (data) => {
        if (clientWs.readyState === WebSocket.OPEN) {
            clientWs.send(data.toString());
        }
    });

    backendWs.on('error', (err) => console.error('[Bridge] Backend WS error:', err.message));
    backendWs.on('close', () => console.log('[Bridge] Backend WS closed'));

    clientWs.on('close', () => {
        backendWs.close();
        console.log('[Bridge] Client disconnected');
    });
});

server.listen(PORT, () => console.log(`[Bridge] Running on port ${PORT}`));

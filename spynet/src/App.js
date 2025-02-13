// App.js
import React, { useState, useEffect } from 'react';
import socketIOClient from 'socket.io-client';
import './App.css';

const ENDPOINT = 'http://192.168.1.81:5000';

// ScannerControls component to start, pause, resume, and stop scanning.
function ScannerControls({ endpoint }) {
  const [network, setNetwork] = useState("");
  const [portStart, setPortStart] = useState(1);
  const [portEnd, setPortEnd] = useState(1024);
  const [timeout, setTimeoutValue] = useState(2);
  const [interval, setIntervalValue] = useState(60);

  const startScanner = () => {
    fetch(`${endpoint}/api/scanner/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ network, port_start: portStart, port_end: portEnd, timeout, interval })
    })
    .then((res) => res.json())
    .then((data) => {
      console.log("Scanner started", data);
    })
    .catch((err) => console.error(err));
  };

  const pauseScanner = () => {
    fetch(`${endpoint}/api/scanner/pause`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    })
    .then((res) => res.json())
    .then((data) => console.log("Scanner paused", data))
    .catch((err) => console.error(err));
  };

  const resumeScanner = () => {
    fetch(`${endpoint}/api/scanner/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    })
    .then((res) => res.json())
    .then((data) => console.log("Scanner resumed", data))
    .catch((err) => console.error(err));
  };

  const stopScanner = () => {
    fetch(`${endpoint}/api/scanner/stop`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    })
    .then((res) => res.json())
    .then((data) => console.log("Scanner stopped", data))
    .catch((err) => console.error(err));
  };

  return (
    <div className="scanner-controls">
      <h2>Scanner Controls</h2>
      <div>
        <label>Network (CIDR):</label>
        <input
          type="text"
          value={network}
          onChange={(e) => setNetwork(e.target.value)}
          placeholder="e.g. 192.168.1.0/24"
        />
      </div>
      <div>
        <label>Port Start:</label>
        <input
          type="number"
          value={portStart}
          onChange={(e) => setPortStart(e.target.value)}
        />
      </div>
      <div>
        <label>Port End:</label>
        <input
          type="number"
          value={portEnd}
          onChange={(e) => setPortEnd(e.target.value)}
        />
      </div>
      <div>
        <label>Timeout (sec):</label>
        <input
          type="number"
          value={timeout}
          onChange={(e) => setTimeoutValue(e.target.value)}
        />
      </div>
      <div>
        <label>Interval (sec):</label>
        <input
          type="number"
          value={interval}
          onChange={(e) => setIntervalValue(e.target.value)}
        />
      </div>
      <button onClick={startScanner}>Start Scanning</button>
      <button onClick={pauseScanner}>Pause</button>
      <button onClick={resumeScanner}>Resume</button>
      <button onClick={stopScanner}>Stop</button>
    </div>
  );
}

function App() {
  const [scanData, setScanData] = useState({});
  const [selectedHost, setSelectedHost] = useState(null);
  const [bannerPort, setBannerPort] = useState('');
  const [bannerResult, setBannerResult] = useState(null);
  const [scanType, setScanType] = useState('popular');
  const [rangeStart, setRangeStart] = useState(1);
  const [rangeEnd, setRangeEnd] = useState(1024);

  useEffect(() => {
    const socket = socketIOClient(ENDPOINT);
    socket.on('scan_update', (data) => {
      console.log('Received scan_update:', data);
      setScanData(data);
    });
    return () => socket.disconnect();
  }, []);

  const handleHostClick = (hostIp) => {
    setSelectedHost(hostIp);
    setBannerResult(null);
    setBannerPort('');
  };

  const startPortScan = () => {
    if (!selectedHost) return;
    const payload = {
      host: selectedHost,
      scan_type: scanType,
      timeout: 2,
    };
    if (scanType === 'range') {
      payload.start_port = parseInt(rangeStart, 10);
      payload.end_port = parseInt(rangeEnd, 10);
    }
    fetch(`${ENDPOINT}/api/command/portscan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then((response) => response.json())
    .then((data) => {
      console.log('Port scan started:', data);
    })
    .catch((err) => console.error('Error starting port scan:', err));
  };

  const startBannerGrab = () => {
    if (!selectedHost || !bannerPort) return;
    const payload = {
      host: selectedHost,
      port: parseInt(bannerPort, 10),
      timeout: 2,
    };
    fetch(`${ENDPOINT}/api/command/bannergrab`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then((response) => response.json())
    .then((data) => {
      console.log('Banner grab result:', data);
      setBannerResult(data.banner);
    })
    .catch((err) => console.error('Error during banner grab:', err));
  };

  const renderHosts = () => {
    return Object.keys(scanData).map((ip) => {
      const host = scanData[ip];
      return (
        <div key={ip} className="host-card" onClick={() => handleHostClick(ip)}>
          <h3>
            {ip} <span className={host.status}>{host.status}</span>
          </h3>
          <p>MAC: {host.mac}</p>
          <p>Vendor: {host.vendor}</p>
          <p>Open Ports: {host.ports ? host.ports.length : 0}</p>
          {host.port_scan_in_progress && (
            <p className="scanning-indicator">Port scan in progress...</p>
          )}
        </div>
      );
    });
  };

  const renderSelectedHostActions = () => {
    if (!selectedHost) return null;
    return (
      <div className="actions-panel">
        <h2>Actions for {selectedHost}</h2>
        <div className="action-group">
          <label>Port Scan Type: </label>
          <select value={scanType} onChange={(e) => setScanType(e.target.value)}>
            <option value="popular">Popular Ports</option>
            <option value="range">Range</option>
            <option value="all">All Ports</option>
          </select>
          {scanType === 'range' && (
            <>
              <input
                type="number"
                placeholder="Start Port"
                value={rangeStart}
                onChange={(e) => setRangeStart(e.target.value)}
              />
              <input
                type="number"
                placeholder="End Port"
                value={rangeEnd}
                onChange={(e) => setRangeEnd(e.target.value)}
              />
            </>
          )}
          <button onClick={startPortScan}>Start Port Scan</button>
        </div>
        <div className="action-group">
          <h3>Port Scan Result:</h3>
          <p>
            {scanData[selectedHost] && scanData[selectedHost].ports
              ? scanData[selectedHost].ports.join(', ')
              : 'No data yet'}
          </p>
        </div>
        <div className="action-group">
          <h3>Banner Grabbing</h3>
          <input
            type="number"
            placeholder="Port for banner grab"
            value={bannerPort}
            onChange={(e) => setBannerPort(e.target.value)}
          />
          <button onClick={startBannerGrab}>Grab Banner</button>
          {bannerResult && (
            <div>
              <h4>Banner:</h4>
              <p>{bannerResult}</p>
            </div>
          )}
        </div>
        <button className="close-btn" onClick={() => setSelectedHost(null)}>
          Close
        </button>
      </div>
    );
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Spynet Dashboard</h1>
      </header>
      <ScannerControls endpoint={ENDPOINT} />
      <main>
        <div className="host-list">{renderHosts()}</div>
        {renderSelectedHostActions()}
      </main>
    </div>
  );
}

export default App;

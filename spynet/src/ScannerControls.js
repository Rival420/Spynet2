// ScannerControls.js
import React, { useState } from 'react';

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
      .then((data) => console.log("Scanner started", data))
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
      <div className="form-row">
        <label htmlFor="network">Network (CIDR):</label>
        <input
          type="text"
          id="network"
          value={network}
          onChange={(e) => setNetwork(e.target.value)}
          placeholder="e.g. 192.168.1.0/24"
        />
      </div>
      <div className="form-row">
        <label htmlFor="portStart">Port Start:</label>
        <input
          type="number"
          id="portStart"
          value={portStart}
          onChange={(e) => setPortStart(e.target.value)}
        />
      </div>
      <div className="form-row">
        <label htmlFor="portEnd">Port End:</label>
        <input
          type="number"
          id="portEnd"
          value={portEnd}
          onChange={(e) => setPortEnd(e.target.value)}
        />
      </div>
      <div className="form-row">
        <label htmlFor="timeout">Timeout (sec):</label>
        <input
          type="number"
          id="timeout"
          value={timeout}
          onChange={(e) => setTimeoutValue(e.target.value)}
        />
      </div>
      <div className="form-row">
        <label htmlFor="interval">Interval (sec):</label>
        <input
          type="number"
          id="interval"
          value={interval}
          onChange={(e) => setIntervalValue(e.target.value)}
        />
      </div>
      <div className="button-group">
        <button onClick={startScanner} className="btn btn-start">Start Scanning</button>
        <button onClick={pauseScanner} className="btn btn-pause">Pause</button>
        <button onClick={resumeScanner} className="btn btn-resume">Resume</button>
        <button onClick={stopScanner} className="btn btn-stop">Stop</button>
      </div>
    </div>
  );
}

export default ScannerControls;
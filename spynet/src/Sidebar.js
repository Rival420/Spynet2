// Sidebar.js
import React, { useState } from 'react';
import './Sidebar.css';

function Sidebar({ endpoint, hideOffline, hideDhcp, setHideOffline, setHideDhcp }) {
  const [network, setNetwork] = useState("");
  const [portStart, setPortStart] = useState(1);
  const [portEnd, setPortEnd] = useState(1024);
  const [timeout, setTimeoutValue] = useState(2);
  const [interval, setIntervalValue] = useState(60);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const toggleCollapse = () => {
    setIsCollapsed(!isCollapsed);
  };

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
    <div className={`sidebar ${isCollapsed ? "collapsed" : ""}`}>
      <button className="toggle-btn" onClick={toggleCollapse}>
        <span className="burger-icon">☰</span>
      </button>
      {!isCollapsed && (
        <div className="controls">
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
            <button className="btn btn-start" onClick={startScanner}>
              Start
            </button>
            <button className="btn btn-pause" onClick={pauseScanner}>
              Pause
            </button>
            <button className="btn btn-resume" onClick={resumeScanner}>
              Resume
            </button>
            <button className="btn btn-stop" onClick={stopScanner}>
              Stop
            </button>
          </div>
          <div className="filter-controls">
          <label className="switch">
              <input
                type="checkbox"
                checked={hideOffline}
                onChange={(e) => setHideOffline(e.target.checked)}
                
              />
              <span className="slider round"></span>
              <span className="switch-text">Hide Offline Hosts</span>
            </label>
            <label className="switch">
              <input
                type="checkbox"
                checked={hideDhcp}
                onChange={(e) => setHideDhcp(e.target.checked)}
              />
              <span className="slider round"></span>
              <span className="switch-text">Hide DHCP Hosts</span>
            </label>
          </div>
        </div>
      )}
    </div>
  );
}

export default Sidebar;

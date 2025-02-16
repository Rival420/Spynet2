// App.js
import React, { useState, useEffect } from 'react';
import socketIOClient from 'socket.io-client';
import Sidebar from './Sidebar';
import './App.css';

const ENDPOINT = 'http://192.168.1.81:5000';

function App() {
  const [scanData, setScanData] = useState({});
  const [selectedHost, setSelectedHost] = useState(null);
  const [bannerPort, setBannerPort] = useState('');
  const [bannerResult, setBannerResult] = useState(null);
  const [scanType, setScanType] = useState('popular');
  const [rangeStart, setRangeStart] = useState(1);
  const [rangeEnd, setRangeEnd] = useState(1024);
  // State to position the floating panel next to the host card
  const [floatingPos, setFloatingPos] = useState({ top: 0, left: 0 });
  // For host details editing
  const [updatedHostname, setUpdatedHostname] = useState("");
  const [updatedIsDhcp, setUpdatedIsDhcp] = useState(false);

  useEffect(() => {
    const socket = socketIOClient(ENDPOINT);
    socket.on('scan_update', (data) => {
      console.log('Received scan_update:', data);
      setScanData(data);
    });
    return () => socket.disconnect();
  }, []);

  // When a host is clicked, record its position and prepopulate details
  const handleHostClick = (hostIp, event) => {
    setSelectedHost(hostIp);
    setBannerResult('');
    setBannerPort('');
    if (scanData[hostIp]) {
      setUpdatedHostname(scanData[hostIp].hostname || "");
      setUpdatedIsDhcp(scanData[hostIp].is_dhcp || false);
    }
    const rect = event.currentTarget.getBoundingClientRect();
    // Position floating panel to the right of the clicked card with a small offset.
    setFloatingPos({ top: rect.top, left: rect.right + 10 });
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

  const updateHostDetails = () => {
    if (!selectedHost) return;
    const payload = {
      ip: selectedHost,
      hostname: updatedHostname,
      is_dhcp: updatedIsDhcp
    };
    fetch(`${ENDPOINT}/api/host/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then((res) => res.json())
      .then((data) => {
        console.log('Host updated:', data);
      })
      .catch((err) => console.error(err));
  };

  const renderHosts = () => {
    // Sort IPs numerically in ascending order.
    const sortedIps = Object.keys(scanData).sort((a, b) => {
      const ipA = a.split('.').map(Number);
      const ipB = b.split('.').map(Number);
      for (let i = 0; i < Math.max(ipA.length, ipB.length); i++) {
        if ((ipA[i] || 0) < (ipB[i] || 0)) return -1;
        if ((ipA[i] || 0) > (ipB[i] || 0)) return 1;
      }
      return 0;
    });
  
    return sortedIps.map((ip) => {
      const host = scanData[ip];
      return (
        <div key={ip} className="host-card" onClick={(e) => handleHostClick(ip, e)}>
          <h3>
            {ip} <span className={host.status}>{host.status}</span>
          </h3>
          <h4>{host.hostname ? `Hostname: ${host.hostname}` : ""}{" "}</h4>
          <p>MAC: {host.mac}</p>
          <p>Vendor: {host.vendor}</p>
          <p className="open-ports">
            Open Ports: {host.ports && host.ports.length ? host.ports.join(', ') : "None"}
          </p>
          {host.port_scan_in_progress && (
            <p className="scanning-indicator">Scanning in progress...</p>
          )}
        </div>
      );
    });
  };
  

  // Floating panel for host actions
  const renderSelectedHostActions = () => {
    if (!selectedHost) return null;
    return (
      <div className="floating-panel" style={{ top: floatingPos.top, left: floatingPos.left }}>
        <h2>Actions for {selectedHost}</h2>
        <div className="action-group">
          <label>Port Scan Type:</label>
          <select value={scanType} onChange={(e) => setScanType(e.target.value)}>
            <option value="popular">Popular Ports</option>
            <option value="range">Range</option>
            <option value="all">All Ports</option>
          </select>
          {scanType === 'range' && (
            <>
              <input type="number" placeholder="Start Port" value={rangeStart} onChange={(e) => setRangeStart(e.target.value)} />
              <input type="number" placeholder="End Port" value={rangeEnd} onChange={(e) => setRangeEnd(e.target.value)} />
            </>
          )}
          <button onClick={startPortScan}>Start Port Scan</button>
        </div>
        <div className="action-group">
          <h3>Banner Grabbing</h3>
          <input type="number" placeholder="Port for banner grab" value={bannerPort} onChange={(e) => setBannerPort(e.target.value)} />
          <button onClick={startBannerGrab}>Grab Banner</button>
          {bannerResult && (
            <div>
              <h4>Banner:</h4>
              <p>{bannerResult}</p>
            </div>
          )}
        </div>
        <div className="action-group">
          <h3>Update Host Details</h3>
          <div>
            <label htmlFor="hostname">Hostname:</label>
            <input type="text" id="hostname" value={updatedHostname} onChange={(e) => setUpdatedHostname(e.target.value)} placeholder="Enter hostname" />
          </div>
          <div>
            <label htmlFor="dhcpFlag">DHCP:</label>
            <input type="checkbox" id="dhcpFlag" checked={updatedIsDhcp} onChange={(e) => setUpdatedIsDhcp(e.target.checked)} />
          </div>
          <button onClick={updateHostDetails}>Save Details</button>
        </div>
        <button className="close-btn" onClick={() => setSelectedHost(null)}>Close</button>
      </div>
    );
  };

  return (
    <div className="App">
      <Sidebar endpoint={ENDPOINT} />
      <div className="main-content" style={{ marginLeft: '300px', padding: '20px' }}>
        <header className="App-header">
          <h1>Spynet Dashboard</h1>
        </header>
        <main>
          <div className="host-list">{renderHosts()}</div>
          {renderSelectedHostActions()}
        </main>
      </div>
    </div>
  );
}

export default App;

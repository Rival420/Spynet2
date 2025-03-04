// App.js
import React, { useState, useEffect } from 'react';
import socketIOClient from 'socket.io-client';
import Sidebar from './Sidebar';
import FloatingMenu from './floating-menu';
import './App.css';

// App.js
const ENDPOINT = window._env_ && window._env_.REACT_APP_ENDPOINT 
  ? window._env_.REACT_APP_ENDPOINT 
  : 'http://localhost:5000';


function App() {
  const [scanData, setScanData] = useState({});
  const [selectedHost, setSelectedHost] = useState(null);
  const [bannerPort, setBannerPort] = useState('');
  const [bannerResult, setBannerResult] = useState(null);
  const [scanType, setScanType] = useState('popular');
  const [rangeStart, setRangeStart] = useState(1);
  const [rangeEnd, setRangeEnd] = useState(1024);
  const [floatingPos, setFloatingPos] = useState({ top: 0, left: 0 });
  const [updatedHostname, setUpdatedHostname] = useState("");
  const [updatedIsDhcp, setUpdatedIsDhcp] = useState(false);

  // Filtering state:
  const [hideOffline, setHideOffline] = useState(false);
  const [hideDhcp, setHideDhcp] = useState(false);

  useEffect(() => {
    const socket = socketIOClient(ENDPOINT);
    socket.on('scan_update', (data) => {
      console.log('Received scan_update:', data);
      setScanData(data);
    });
    return () => socket.disconnect();
  }, []);

  const handleHostClick = (hostIp, event) => {
    setSelectedHost(hostIp);
    setBannerResult('');
    setBannerPort('');

    if (scanData[hostIp]) {
      setUpdatedHostname(scanData[hostIp].hostname || "");
      setUpdatedIsDhcp(scanData[hostIp].is_dhcp || false);
    }

    const rect = event.currentTarget.getBoundingClientRect();
    const panelWidth = 320; // Width of floating panel
    const panelHeight = 300; // Estimated height of the floating panel
    const padding = 20; // Padding to keep it inside the viewport

    let left = rect.right + 10; // Default position to the right of the host card
    let top = rect.top;

    // Prevent the menu from going outside the right edge
    if (left + panelWidth > window.innerWidth - padding) {
        left = rect.left - panelWidth - 10; // Move it to the left side instead
    }

    // Prevent the menu from going below the bottom edge
    if (top + panelHeight > window.innerHeight - padding) {
        top = window.innerHeight - panelHeight - padding;
    }

    setFloatingPos({ top, left });
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
      .then((data) => console.log('Port scan started:', data))
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
      .then((data) => console.log('Host updated:', data))
      .catch((err) => console.error(err));
  };

  const performMacLookup = () => {
    if (!selectedHost) return;
    const payload = { host: selectedHost };
    fetch(`${ENDPOINT}/api/command/maclookup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log("MAC Lookup result:", data);
        alert(`Vendor for ${selectedHost}: ${data.vendor}`);
      })
      .catch((err) => console.error("Error performing MAC lookup:", err));
  };

  const renderHosts = () => {
    const sortedIps = Object.keys(scanData).sort((a, b) => {
      const ipA = a.split('.').map(Number);
      const ipB = b.split('.').map(Number);
      for (let i = 0; i < Math.max(ipA.length, ipB.length); i++) {
        if ((ipA[i] || 0) < (ipB[i] || 0)) return -1;
        if ((ipA[i] || 0) > (ipB[i] || 0)) return 1;
      }
      return 0;
    });

    const filteredIps = sortedIps.filter(ip => {
      const host = scanData[ip];
      if (hideOffline && host.status === 'offline') return false;
      if (hideDhcp && host.is_dhcp) return false;
      return true;
    });

    return filteredIps.map((ip) => {
      const host = scanData[ip];
      return (
        <div key={ip} className="host-card" onClick={(e) => handleHostClick(ip, e)}>
          <h3>
            {ip} <span className={host.status}>{host.status}</span>
          </h3>
          <h4>{host.hostname ? `Hostname: ${host.hostname}` : ""}</h4>
          <p>MAC: {host.mac}</p>
          <p>Vendor: {host.vendor}</p>
          <p className="open-ports">
            Open Ports: {host.ports && host.ports.length ? host.ports.join(', ') : "None"}
          </p>
          {host.port_scan_in_progress && (
            <p className="scanning-indicator">Scanning in progress...</p>
          )}
          <p className="dhcp-flag">
            Type: {host.is_dhcp ? "DHCP" : "Static"}
          </p>
        </div>
      );
    });
  };

  return (
    <div className="App">
      <Sidebar 
        endpoint={ENDPOINT} 
        hideOffline={hideOffline} 
        hideDhcp={hideDhcp} 
        setHideOffline={setHideOffline} 
        setHideDhcp={setHideDhcp}
      />
      <div className="main-content">
        <header className="App-header">
          <h1>Spynet Dashboard</h1>
        </header>
        <main>
          <div className="host-list">{renderHosts()}</div>
          {selectedHost && (
            <FloatingMenu
              selectedHost={selectedHost}
              floatingPos={floatingPos}
              updatedHostname={updatedHostname}
              updatedIsDhcp={updatedIsDhcp}
              onHostnameChange={(e) => setUpdatedHostname(e.target.value)}
              onIsDhcpChange={(e) => setUpdatedIsDhcp(e.target.checked)}
              updateHostDetails={updateHostDetails}
              scanType={scanType}
              onScanTypeChange={(e) => setScanType(e.target.value)}
              rangeStart={rangeStart}
              onRangeStartChange={(e) => setRangeStart(e.target.value)}
              rangeEnd={rangeEnd}
              onRangeEndChange={(e) => setRangeEnd(e.target.value)}
              startPortScan={startPortScan}
              bannerPort={bannerPort}
              onBannerPortChange={(e) => setBannerPort(e.target.value)}
              startBannerGrab={startBannerGrab}
              bannerResult={bannerResult}
              performMacLookup={performMacLookup}
              onClose={() => setSelectedHost(null)}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;

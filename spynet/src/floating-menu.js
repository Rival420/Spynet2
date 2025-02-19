// floating-menu.js
import React from 'react';
import './floating-menu.css';

const FloatingMenu = ({
  selectedHost,
  floatingPos,
  updatedHostname,
  updatedIsDhcp,
  onHostnameChange,
  onIsDhcpChange,
  updateHostDetails,
  scanType,
  onScanTypeChange,
  rangeStart,
  onRangeStartChange,
  rangeEnd,
  onRangeEndChange,
  startPortScan,
  bannerPort,
  onBannerPortChange,
  startBannerGrab,
  bannerResult,
  performMacLookup,
  onClose
}) => {
  if (!selectedHost) return null;
  
  return (
    <div className="floating-panel" style={{ top: floatingPos.top, left: floatingPos.left }}>
      <button className="close-btn" onClick={onClose}>&times;</button>
      <h2>Actions for {selectedHost}</h2>
      
      {/* Group 1: Update Host Details */}
      <div className="action-group update-details">
        <h3>Host Details</h3>
        <div className="form-row">
          <label htmlFor="hostname">Hostname:</label>
          <input
            type="text"
            id="hostname"
            value={updatedHostname}
            onChange={onHostnameChange}
            placeholder="Enter hostname"
          />
        </div>
        <div className="form-row">
          <label htmlFor="dhcpFlag">DHCP:</label>
          <label className="switch">
            <input
              type="checkbox"
              id="dhcpFlag"
              checked={updatedIsDhcp}
              onChange={onIsDhcpChange}
            />
            <span className="slider round"></span>
          </label>
        </div>
        <button className="btn btn-save" onClick={updateHostDetails}>
          Save Details
        </button>
      </div>
      
      {/* Group 2: Port Scanning */}
      <div className="action-group port-scan">
        <h3>Port Scan</h3>
        <div className="form-row">
          <label>Scan Type:</label>
          <select value={scanType} onChange={onScanTypeChange}>
            <option value="popular">Popular Ports</option>
            <option value="range">Range</option>
            <option value="all">All Ports</option>
          </select>
        </div>
        {scanType === 'range' && (
          <div className="form-row">
            <input
              type="number"
              placeholder="Start Port"
              value={rangeStart}
              onChange={onRangeStartChange}
            />
            <input
              type="number"
              placeholder="End Port"
              value={rangeEnd}
              onChange={onRangeEndChange}
            />
          </div>
        )}
        <button className="btn btn-action" onClick={startPortScan}>
          Start Port Scan
        </button>
      </div>
      
      {/* Group 3: Banner Grabbing */}
      <div className="action-group banner-grab">
        <h3>Banner Grabbing</h3>
        <div className="form-row">
          <input
            type="number"
            placeholder="Port for Banner"
            value={bannerPort}
            onChange={onBannerPortChange}
          />
        </div>
        <button className="btn btn-action" onClick={startBannerGrab}>
          Grab Banner
        </button>
        {bannerResult && (
          <div className="banner-result">
            <h4>Banner:</h4>
            <p>{bannerResult}</p>
          </div>
        )}
      </div>
      
      {/* Group 4: MAC Vendor Lookup */}
      <div className="action-group mac-lookup">
        <button className="btn btn-action" onClick={performMacLookup}>
          MAC Vendor Lookup
        </button>
      </div>
    </div>
  );
};

export default FloatingMenu;

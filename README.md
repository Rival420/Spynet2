# Spynet

Spynet is a modular network scanning tool designed for IT professionals and hobbiest with an ever growing IT landscape in their homes. It performs ARP scans to detect live hosts on your network and then conducts SYN-based port scans on those hosts. The results are displayed in a live-updating, modern React dashboard with a dark theme.

## Why Spynet?

In today's network and IOT landscape, staying on top of your network's status is essential. Spynet provides an up-to-date overview of active hosts, open ports, and device details (including MAC vendor information), helping you monitor your network in real time. Whether you’re a hobbiest or a network engineer, Spynet gives you the visibility you need to know your environment.

## Features

- **ARP Scanning:** Quickly discover live hosts on a specified network range.
- **Port Scanning:** Perform SYN-based port scans on discovered hosts.
- **Live Dashboard:** A React-based dashboard updates in real time via Socket.IO.
- **MAC Vendor Lookup:** Identify device vendors based on their MAC addresses.

> **Note:** This version does not yet include some advanced features (see the TODO section below).

## Getting Started

### Prerequisites

- **Python 3.8+**
- **pip**
- **Node.js and npm**
- **sudo/administrator privileges** (for raw socket operations)

### Backend Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Rival420/spynet2.git
   cd spynet
   ```

2. **Create and activate a Python virtual environment:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install required Python packages:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Start the Python server:**

   The server requires administrative privileges for raw socket access.

   ```bash
   sudo ./venv/bin/python server.py
   ```

### Frontend Setup

1. **Navigate to the React app directory:**

   ```bash
   cd spynet
   ```

2. **Install Node dependencies:**

   ```bash
   npm install
   ```

3. **Configure the API endpoint:**

   Create a `.env` file in the React project root with the following line:

   ```env
   REACT_APP_API_ENDPOINT=http://<host>:5000
   ```

   *Adjust the IP address/port if needed.*

4. **Start the React development server:**

   ```bash
   npm start
   ```

   Your dashboard should now be accessible (e.g., at `http://localhost:3000`), and it will connect to your backend for live updates.

## Usage

- **Live Dashboard:** Once both backend and frontend are running, the dashboard will show live hosts discovered by ARP scans, along with their MAC addresses, vendor information, and port scan status.
- **On-Demand Scans:** Click on a host in the dashboard to bring up controls to initiate additional port scans or banner grabbing for that specific host.

## TODO / Future Features

The following features are planned for future updates:

- [x] **Database Integration:**  
   Persist host scan data in a database (e.g., SQLite with SQLAlchemy) so that results are retained across reboots or server restarts.

- [x] **DHCP Flag for Dynamic IPs:**  
   Allow setting a DHCP flag on certain IPs via the GUI so that these entries are refreshed (or removed) automatically after a configurable interval.

- [x] **Hostname Assignment:**  
   Provide an option in the GUI for users to assign custom hostnames to devices for easier identification.

- [x] **GUI-Based Scanner Control:**  
   Add controls in the React dashboard to start, stop, and pause scanning, and allow configuration of scanning parameters (like scan interval and port range) through the GUI.

## Contributing

Contributions are welcome! Feel free to fork the repository, open issues, or submit pull requests.

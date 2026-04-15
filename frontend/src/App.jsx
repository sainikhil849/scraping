import React, { useState } from 'react';
import axios from 'axios';
import { 
  Search, MapPin, Tag, Download, Filter, 
  Loader2, Link2, Calendar, Compass, Layers, CheckSquare, Square 
} from 'lucide-react';
import './App.css';

function App() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Dashboard Form State
  const [city, setCity] = useState('Hyderabad');
  const [maxEvents, setMaxEvents] = useState(10);
  const [selectedPlatforms, setSelectedPlatforms] = useState(['BookMyShow']);

  const platforms = [
    "BookMyShow",
    "District",
    "Urbanaut",
    "MeraEvents",
    "Swiggy Scenes",
    "Skillbox",
    "Sort My Scene",
    "Meetup"
  ];

  const togglePlatform = (p) => {
    if (selectedPlatforms.includes(p)) {
      setSelectedPlatforms(selectedPlatforms.filter(item => item !== p));
    } else {
      setSelectedPlatforms([...selectedPlatforms, p]);
    }
  };

  const handleScrape = async (e) => {
    e.preventDefault();
    if (selectedPlatforms.length === 0) {
      setError("Please select at least one platform.");
      return;
    }
    
    setLoading(true);
    setError(null);
    setEvents([]);

    try {
      const response = await axios.post('http://localhost:8000/api/scrape', {
        location: city,
        max_events: parseInt(maxEvents),
        platforms: selectedPlatforms
      });

      // The backend returns a list of events directly now
      const fetchedEvents = Array.isArray(response.data) ? response.data : response.data.events || [];
      setEvents(fetchedEvents);
      
      if (fetchedEvents.length === 0) {
        setError("No events discovered for the selected location and platforms.");
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Connection error. Ensure backend is running.");
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
      try {
          const response = await axios.post('http://localhost:8000/api/export', events, {
              responseType: 'blob'
          });
          const url = window.URL.createObjectURL(new Blob([response.data]));
          const link = document.createElement('a');
          link.href = url;
          link.setAttribute('download', 'events.xlsx');
          document.body.appendChild(link);
          link.click();
          link.remove();
      } catch (err) {
          setError("Failed to download Excel file.");
      }
  };

  return (
    <div className="dashboard-container">
      <div className="bg-shape circle-1"></div>
      <div className="bg-shape circle-2"></div>

      <div className="main-content">
        <header className="glass-panel header">
          <div className="logo">
            <Compass className="icon pulse" />
            <h1>Event Intelligence <span>Engineer</span></h1>
          </div>
          <div className="status-badge">Professional Mode</div>
        </header>

        <div className="grid-layout">
          {/* Production Sidebar */}
          <aside className="glass-panel sidebar">
            <h2><Search className="icon" /> Configuration</h2>
            <form onSubmit={handleScrape} className="scrape-form">
              <div className="form-group">
                <label><MapPin className="icon-sm" /> City</label>
                <input 
                  type="text" 
                  value={city} 
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="e.g. Hyderabad" 
                />
              </div>

              <div className="form-group">
                <label>⭐ Maximum Events</label>
                <input 
                  type="number" 
                  required
                  min="1"
                  value={maxEvents} 
                  onChange={(e) => setMaxEvents(e.target.value)} 
                />
              </div>

              <div className="form-group">
                <label><Layers className="icon-sm" /> Platform Selection</label>
                <div className="platform-selector-grid">
                  {platforms.map(p => (
                    <div 
                      key={p} 
                      className={`platform-option ${selectedPlatforms.includes(p) ? 'active' : ''}`}
                      onClick={() => togglePlatform(p)}
                    >
                      {selectedPlatforms.includes(p) ? <CheckSquare size={16}/> : <Square size={16}/>}
                      <span>{p}</span>
                    </div>
                  ))}
                </div>
              </div>

              <button type="submit" className="primary-btn" disabled={loading}>
                {loading ? <><Loader2 className="spinner" /> Scraping...</> : "Search Events"}
              </button>
            </form>
          </aside>

          {/* Results Main Area */}
          <main className="results-area">
            {error && <div className="error-panel">⚠️ {error}</div>}

            <div className="glass-panel results-container">
              <div className="results-header">
                <h2><Filter className="icon" /> Verified Events</h2>
                {events.length > 0 && (
                  <button onClick={handleDownload} className="excel-btn">
                    <Download size={18} /> Download Excel
                  </button>
                )}
              </div>

              {loading ? (
                <div className="loading-state">
                  <Loader2 className="global-spinner" />
                  <p>Opening visible browser for direct scraping...</p>
                </div>
              ) : events.length > 0 ? (
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>Event Name</th>
                        <th>Date</th>
                        <th>Price</th>
                        <th>Platform</th>
                        <th>City</th>
                        <th>Description</th>
                        <th>View Link</th>
                      </tr>
                    </thead>
                    <tbody>
                      {events.map((ev, idx) => (
                        <tr key={idx}>
                          <td className="bold">{ev.event_name}</td>
                          <td>{ev.event_date}</td>
                          <td className="price">{ev.price === -1 ? "N/A" : `₹${ev.price}`}</td>
                          <td><span className="platform-tag">{ev.platform}</span></td>
                          <td>{ev.city}</td>
                          <td className="desc-cell">{ev.description}</td>
                          <td>
                            <a href={ev.event_url} target="_blank" rel="noopener noreferrer" className="view-link">
                              <Link2 size={14} /> View Link
                            </a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  <Compass size={48} className="empty-icon" />
                  <p>Ready to scrape. Select platforms and click Search.</p>
                </div>
              )}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

export default App;

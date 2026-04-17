import React from 'react';
import './EventCard.css';

const EventCard = ({ event, onViewClick }) => {
  const isCritical = event.status === 'critical';
  const borderColorClass = isCritical ? 'border-red' : 'border-green';
  const statusColorClass = isCritical ? 'text-red' : 'text-green';

  return (
    <div className={`event-card ${borderColorClass}`}>
      <div className="event-card-header">
        <div className={`event-status ${statusColorClass}`}>
          {isCritical ? (
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          )}
          <span>{event.statusText}</span>
        </div>
        <span className="event-time">{event.time}</span>
      </div>

      <h3 className="event-title">{event.title}</h3>

      <div className="event-details">
        <div className="detail-item">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M4 18v3h3v-3h10v3h3v-6H4v3zm15-8h3v3h-3v-3zM2 10h3v3H2v-3zm15 3H7V5c0-1.1.9-2 2-2h6c1.1 0 2 .9 2 2v8z"/>
          </svg>
          <span>{event.location}</span>
        </div>
        <div className="detail-item">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/>
          </svg>
          <span>{event.duration}</span>
        </div>
      </div>

      <div className="event-actions">
        <button className="btn-contact-supervisor">
          الاتصال بالمراقب
          <img src={process.env.PUBLIC_URL + '/icons/phone.png'} alt="Call Supervisor" style={{ width: '18px', height: '18px', objectFit: 'contain' }} />
        </button>
        <button className="btn-view-state" onClick={onViewClick}>
          عرض الحالة
          <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M8 5v14l11-7z" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default EventCard;

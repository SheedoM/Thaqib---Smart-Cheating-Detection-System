import React from 'react';
import './CameraCard.css';

const CameraCard = ({ camera, onClick }) => {
  const isSuspicious = camera.status === 'suspicious';

  return (
    <div
      className={`camera-card ${isSuspicious ? 'suspicious' : ''}`}
      onClick={() => onClick && onClick(camera)}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
    >
      <div
        className="camera-feed-bg"
        style={{ backgroundImage: `url(${process.env.PUBLIC_URL + camera.img})` }}
      ></div>

      {isSuspicious && <div className="suspicious-gradient-overlay"></div>}

      <div className="camera-card-top-left">
        <div className="rec-badge-small">
          <div className="rec-dot-small"></div>
          <span>REC</span>
        </div>
      </div>

      <div className="camera-card-top-right">
        <div className="camera-name-badge">
          <span>{camera.name}</span>
          <div className={`status-dot ${isSuspicious ? 'red' : 'green'}`}></div>
        </div>
      </div>

      <div className="camera-card-bottom-right">
        <div className="camera-stats-box">
          <p>FPS: 30 • BITRATE: 4.2Mbps</p>
        </div>
        <div className="camera-stats-box">
          <p>CODEC: H.265 • RES: 1080p</p>
        </div>
      </div>

      {isSuspicious && (
        <div className="suspicious-overlay-box">
          <div className="target-box">
            <div className="scan-corners"></div>
            <div className="suspicious-tag">حركة مشبوهة</div>
            <div className="suspicious-target-text">
              <p>الطالب</p>
              <p>{camera.text}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CameraCard;

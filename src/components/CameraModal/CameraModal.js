import React from 'react';
import './CameraModal.css';

const CameraModal = ({ isOpen, onClose, camera, showPlayIcon }) => {
  if (!isOpen) return null;

  // Use the provided camera or fallback to mock
  const modalCamera = camera?.img ? camera : {
    name: 'كاميرا 2 - وسط',
    status: 'normal',
    img: '/classroom.jpg'
  };

  const isSuspicious = modalCamera.status === 'suspicious';

  return (
    <div className="camera-modal-overlay" onClick={onClose} dir="rtl">
      <div className="camera-modal-container" onClick={(e) => e.stopPropagation()}>
        <div 
          className="modal-camera-bg" 
          style={{ backgroundImage: `url(${process.env.PUBLIC_URL + modalCamera.img})` }}
        ></div>

        {showPlayIcon && (
          <div className="camera-play-overlay-modal">
            <img src={process.env.PUBLIC_URL + '/icons/play.png'} alt="Play Video" style={{ width: '120px', height: '120px', objectFit: 'contain' }} />
          </div>
        )}
        
        {isSuspicious && <div className="suspicious-gradient-overlay-modal"></div>}

        <div className="modal-top-left">
          <div className="rec-badge-modal">
            <span>REC</span>
            <div className="rec-dot-modal"></div>
          </div>
        </div>

        <div className="modal-top-right">
          <div className="camera-name-badge-modal">
            <span>{modalCamera.name || 'كاميرا 2 - وسط'}</span>
            <div className={`status-dot-modal ${isSuspicious ? 'red' : 'green'}`}></div>
          </div>
        </div>

        <div className="modal-bottom-right">
          <div className="camera-stats-box-modal">
            <p>FPS: 30 • BITRATE: 4.2Mbps</p>
          </div>
          <div className="camera-stats-box-modal">
            <p>CODEC: H.265 • RES: 1080p</p>
          </div>
        </div>

      </div>
    </div>
  );
};

export default CameraModal;

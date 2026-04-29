import React, { useState } from 'react';
import './Dashboard.css';
import EventCard from '../../components/EventCard/EventCard';
import CameraCard from '../../components/CameraCard/CameraCard';
import Header from '../../components/Header/Header';
import CameraModal from '../../components/CameraModal/CameraModal';

const Dashboard = ({ activeTab, setActiveTab }) => {
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [isFromEvents, setIsFromEvents] = useState(false);
  const [viewMode, setViewMode] = useState('events'); // 'events' | 'cameras'

  const openCameraModal = (event, fromEvents = false) => {
    setSelectedEvent(event);
    setIsFromEvents(fromEvents);
  };

  const closeCameraModal = () => {
    setSelectedEvent(null);
  };
  const rooms = [
    {
      id: 101,
      name: "قاعة 101",
      cameras: [
        { id: 'c3', name: 'كاميرا 1 - يمين', status: 'suspicious', text: 'رقم 3&4', img: '/classroom.jpg' },
        { id: 'c2', name: 'كاميرا 2 - وسط', status: 'normal', img: '/classroom.jpg' },
        { id: 'c1', name: 'كاميرا 3 - يسار', status: 'normal', img: '/classroom.jpg' }
      ],
      events: [
        {
          id: 3,
          time: "10:23:15",
          status: "critical",
          statusText: "أولوية قصوى",
          title: "غش من الجار",
          location: "الصف 3، المقاعد 7-8",
          duration: "مستمر: 23ث"
        },
        {
          id: 1,
          time: "10:23:15",
          status: "resolved",
          statusText: "تم حلها",
          title: "اكتشاف أوراق",
          location: "الصف 3، المقاعد 7-8",
          duration: "مستمر: 23ث"
        },
        {
          id: 2,
          time: "10:23:15",
          status: "resolved",
          statusText: "تم حلها",
          title: "اكتشاف أوراق",
          location: "الصف 3، المقاعد 7-8",
          duration: "مستمر: 23ث"
        }
      ]
    },
    {
      id: 102,
      name: "قاعة 102",
      cameras: [
        { id: 'c6', name: 'كاميرا 1 - يمين', status: 'normal', img: '/classroom.jpg' },
        { id: 'c5', name: 'كاميرا 2 - وسط', status: 'normal', img: '/classroom.jpg' },
        { id: 'c4', name: 'كاميرا 3 - يسار', status: 'normal', img: '/classroom.jpg' }
      ],
      events: [
        {
          id: 6,
          time: "10:23:15",
          status: "critical",
          statusText: "أولوية قصوى",
          title: "غش من الجار",
          location: "الصف 3، المقاعد 7-8",
          duration: "مستمر: 23ث"
        },
        {
          id: 4,
          time: "10:23:15",
          status: "resolved",
          statusText: "تم حلها",
          title: "اكتشاف أوراق",
          location: "الصف 3، المقاعد 7-8",
          duration: "مستمر: 23ث"
        },
        {
          id: 5,
          time: "10:23:15",
          status: "resolved",
          statusText: "تم حلها",
          title: "اكتشاف أوراق",
          location: "الصف 3، المقاعد 7-8",
          duration: "مستمر: 23ث"
        }
      ]
    }
  ];

  return (
    <div className="dashboard-layout" dir="rtl">
      {/* Dynamic Purple Header Background */}
      <div className="dashboard-header-bg">
        <div className="decorative-overlay"></div>
      </div>

      <Header activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="dashboard-main">
        <div className="dashboard-controls">
          <div className="view-toggles">
            <div className={`latest-events-btn ${viewMode === 'events' ? 'active' : ''}`} onClick={() => setViewMode('events')}>
              أخر الحالات
              <img src={process.env.PUBLIC_URL + '/icons/history.png'} alt="Latest Events" style={{ width: '20px', height: '20px', objectFit: 'contain' }} />
            </div>
            <div className={`camera-view-btn ${viewMode === 'cameras' ? 'active' : ''}`} onClick={() => setViewMode('cameras')}>
              عرض الكاميرات
            </div>
          </div>

          <div className="room-selector-dropdown">
            القاعة
            <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} alt="Chevron" style={{ width: '16px', height: '16px', objectFit: 'contain' }} />
          </div>
        </div>

        <div className="dashboard-content">
          {rooms.map(room => (
            <div key={room.id} className="room-section fade-in">
              <div className="room-header-bar">
                <h2 className="room-title">{room.name}</h2>
                {viewMode === 'cameras' && (
                  <button className="room-contact-button">
                    <img src={process.env.PUBLIC_URL + '/icons/phone.png'} alt="Contact" className="contact-icon-img" />
                    <span>الاتصال بالمراقب</span>
                  </button>
                )}
              </div>
              <div className="events-grid">
                {viewMode === 'events' ? (
                  room.events.map(event => (
                    <EventCard
                      key={event.id}
                      event={event}
                      onViewClick={() => openCameraModal(event, true)}
                    />
                  ))
                ) : (
                  room.cameras && room.cameras.map(camera => (
                    <CameraCard
                      key={camera.id}
                      camera={camera}
                      onClick={(cam) => openCameraModal(cam, false)}
                    />
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
      </main>

      <CameraModal
        isOpen={selectedEvent !== null}
        onClose={closeCameraModal}
        camera={selectedEvent}
        showPlayIcon={isFromEvents}
      />
    </div>
  );
};

export default Dashboard;

import React, { useState } from 'react';
import './Rooms.css';
import Header from '../../components/Header/Header';
import DeleteModal from './DeleteModal';
import EditAddModal from './EditAddModal';

const mockRooms = [
  { id: 1, name: 'قاعة 101B', students: 200, status: 'available' },
  { id: 2, name: 'قاعة 102B', students: 100, status: 'available' },
  { id: 3, name: 'قاعة 103B', students: 160, status: 'unavailable' },
  { id: 4, name: 'قاعة 104B', students: 250, status: 'available' },
  { id: 5, name: 'قاعة 201B', students: 150, status: 'unavailable' },
  { id: 6, name: 'قاعة 202B', students: 300, status: 'available' },
  { id: 7, name: 'قاعة 203B', students: 80, status: 'available' },
  { id: 8, name: 'قاعة 204B', students: 190, status: 'unavailable' }
];

const Rooms = ({ activeTab, setActiveTab }) => {
  const [editAddModalProps, setEditAddModalProps] = useState({ isOpen: false, mode: 'add', roomData: null });
  
  // Real state
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [selectedRoom, setSelectedRoom] = useState(null);

  const openDeleteModal = (room) => {
    setSelectedRoom(room);
    setIsDeleteOpen(true);
  };

  const openEditModal = (room) => {
    setEditAddModalProps({ isOpen: true, mode: 'edit', roomData: room });
  };

  const openAddModal = () => {
    setEditAddModalProps({ isOpen: true, mode: 'add', roomData: null });
  };

  return (
    <div className="dashboard-layout" dir="rtl">
      {/* Background container just like Dashboard */}
      <div className="dashboard-header-bg">
        <div className="decorative-overlay"></div>
      </div>

      <Header activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="dashboard-main rooms-main">
        <div className="rooms-header-controls">
          <div className="halls-status-btn">
            <span className="halls-text">القاعات</span>
            <img src={process.env.PUBLIC_URL + '/icons/cil_room.svg'} alt="Rooms" className="halls-icon" />
          </div>

          <div className="search-box-container">
            <div className="search-box">
              <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} alt="Chevron" className="search-chevron" />
              <span className="search-placeholder">بحث </span>
            </div>
          </div>
        </div>

        <div className="rooms-grid-container fade-in">
          <div className="rooms-list-header">
            <h2 className="rooms-section-title">القاعات</h2>
            <button className="add-room-btn" onClick={openAddModal}>
              <span>إضافة قاعة</span>
              <img src={process.env.PUBLIC_URL + '/icons/gg_add.svg'} alt="Add" className="add-icon" />
            </button>
          </div>

          <div className="rooms-grid">
            {mockRooms.map(room => (
              <div key={room.id} className="room-card">
                <div className="room-card-top-half">
                  <div className="room-students-badge">
                    {room.students} طالب
                  </div>
                  <div className={`room-status-badge ${room.status === 'available' ? 'available' : 'unavailable'}`}>
                    {room.status === 'available' ? 'متاحة' : 'غير متاحة'}
                  </div>
                </div>
                
                <div className="room-card-bottom-half">
                  <div className="room-avatar-container">
                    <img src={process.env.PUBLIC_URL + '/classroom.png'} alt="Room" className="room-avatar" />
                  </div>
                  
                  <h3 className="room-card-name">قاعة {room.name.replace('قاعة ', '')}</h3>
                  
                  <div className="room-card-actions">
                    <button className="edit-btn" onClick={() => openEditModal(room)}>
                      <span>تعديل</span>
                      <img src={process.env.PUBLIC_URL + '/icons/fi_1827933.svg'} alt="Edit" className="action-icon" />
                    </button>
                    <button className="delete-btn-new" onClick={() => openDeleteModal(room)}>
                      <img src={process.env.PUBLIC_URL + '/icons/fi_3405244.svg'} alt="Delete" className="action-icon" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>

      <DeleteModal 
        isOpen={isDeleteOpen} 
        onClose={() => setIsDeleteOpen(false)} 
      />

      <EditAddModal 
        isOpen={editAddModalProps.isOpen} 
        mode={editAddModalProps.mode}
        roomData={editAddModalProps.roomData}
        onClose={() => setEditAddModalProps({ ...editAddModalProps, isOpen: false })} 
      />
    </div>
  );
};

export default Rooms;

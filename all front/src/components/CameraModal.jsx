export default function CameraModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 flex justify-center items-center">

      <div className="relative w-[70%]">
        <img src="https://via.placeholder.com/800x400" className="rounded-xl" />

        <span className="absolute top-2 left-2 text-red-500">● REC</span>

        <button
          onClick={onClose}
          className="absolute top-2 right-2 bg-red-500 text-white px-3 py-1 rounded"
        >
          إغلاق
        </button>
      </div>

    </div>
  );
}
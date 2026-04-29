export default function HallCard({ hall, onDelete }) {
  return (
    <div className="bg-white p-4 rounded-xl shadow">

      <div className="flex justify-between">
        <span className={hall.status === "available" ? "text-green-500" : "text-red-500"}>
          {hall.status === "available" ? "متاحة" : "غير متاحة"}
        </span>

        <span>{hall.students} طالب</span>
      </div>

      <h3 className="text-center mt-3 font-bold">
        قاعة {hall.id}
      </h3>

      <div className="flex justify-between mt-4">
        <button onClick={onDelete} className="text-red-500">🗑</button>
        <button className="bg-purple-700 text-white px-3 py-1 rounded">
          تعديل
        </button>
      </div>

    </div>
  );
}
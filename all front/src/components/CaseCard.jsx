export default function CaseCard({ data }) {
  return (
    <div className={`p-4 rounded-xl shadow bg-white border-r-4 ${
      data.status === "danger" ? "border-red-500" : "border-green-500"
    }`}>

      <p className="text-sm text-gray-400">{data.time}</p>

      <h3 className="font-bold mt-2">{data.title}</h3>

      <p className="text-sm">{data.hall}</p>

      <div className="flex gap-2 mt-4">
        <button className="bg-blue-700 text-white px-3 py-1 rounded">
          عرض الحالة
        </button>
        <button className="bg-green-500 text-white px-3 py-1 rounded">
          اتصال
        </button>
      </div>

    </div>
  );
}
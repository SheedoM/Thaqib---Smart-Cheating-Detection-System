export default function Navbar() {
  return (
    <div style={{
      background: "linear-gradient(90deg, #4b0082, #6a0dad)",
      color: "white",
      padding: "20px",
      borderRadius: "15px",
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center"
    }}>

      <h2>THAQIB</h2>

      <div>
        <span style={{margin: "10px", cursor: "pointer"}}>الرئيسية</span>
        <span style={{margin: "10px", cursor: "pointer"}}>القاعات</span>
        <span style={{margin: "10px", cursor: "pointer"}}>الحالات</span>
      </div>

    </div>
  );
}
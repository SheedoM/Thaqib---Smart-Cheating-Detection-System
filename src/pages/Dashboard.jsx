import Navbar from "../components/Navbar";
import CaseCard from "../components/CaseCard";
import HallCard from "../components/HallCard";
import { cases } from "../data/cases";
import { halls } from "../data/halls";

function Dashboard() {
  return (
    <div className="dashboard">
      <Navbar />

      <div className="container">
        <h1 className="title">Dashboard</h1>

        {/* Cases Section */}
        <section className="section">
          <div className="section-header">
            <h2>Cases</h2>
            <button className="btn">View All</button>
          </div>

          <div className="grid">
            {cases.slice(0, 3).map((item) => (
              <CaseCard key={item.id} caseItem={item} />
            ))}
          </div>
        </section>

        {/* Halls Section */}
        <section className="section">
          <div className="section-header">
            <h2>Halls</h2>
            <button className="btn">View All</button>
          </div>

          <div className="grid">
            {halls.slice(0, 3).map((item) => (
              <HallCard key={item.id} hall={item} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

export default Dashboard;
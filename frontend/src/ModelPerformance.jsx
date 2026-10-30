import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Crosshair,
  Target,
} from 'lucide-react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import './ModelPerformance.css'

const metrics = {
  binaryAccuracy: 99.8732,
  attackAccuracy: 99.2719,
  binary: {
    precision: 99.7868,
    recall: 99.8408,
    f1: 99.8138,
  },
  attack: {
    precision: 93.5801,
    recall: 86.1721,
    f1: 87.4657,
  },
}

const categories = [
  { name: 'BENIGN', precision: 99.73, recall: 99.68, f1: 99.71, support: 6000 },
  { name: 'Bot', precision: 97.28, recall: 100, f1: 98.62, support: 393 },
  { name: 'Brute Force', precision: 98.08, recall: 96.61, f1: 97.34, support: 3069 },
  { name: 'DDoS', precision: 99.98, recall: 99.97, f1: 99.97, support: 6000 },
  { name: 'DoS', precision: 99.85, recall: 99.83, f1: 99.84, support: 6000 },
  { name: 'Heartbleed', precision: 100, recall: 100, f1: 100, support: 2 },
  { name: 'Infiltration', precision: 100, recall: 85.71, f1: 92.31, support: 7 },
  { name: 'PortScan', precision: 99.97, recall: 99.95, f1: 99.96, support: 6000 },
  { name: 'SQL Injection', precision: 100, recall: 25, f1: 40, support: 4 },
  { name: 'XSS', precision: 40.91, recall: 54.96, f1: 46.91, support: 131 },
]

function MetricCard({ icon: Icon, label, value, description, tone }) {
  return (
    <article className="performance-card">
      <div className={`performance-icon ${tone}`}>
        <Icon size={20} />
      </div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{description}</small>
    </article>
  )
}

export default function ModelPerformance() {
  const chartData = categories.filter(item => item.name !== 'BENIGN')

  return (
    <div className="performance-page">
      <header className="performance-header">
        <div>
          <span className="eyebrow">MODEL EVALUATION</span>
          <h2>Model Performance</h2>
          <p>
            Evaluation metrics from the saved CICIDS2017 held-out test reports.
          </p>
        </div>
        <div className="evaluation-tag">
          <CheckCircle2 size={16} />
          Saved evaluation results
        </div>
      </header>

      <div className="performance-notice">
        <Activity size={19} />
        <div>
          <strong>Test-set performance, not a real-world guarantee</strong>
          <p>
            The reports cover 27,606 test examples. Results on new network
            traffic may differ, especially for rare attack categories.
          </p>
        </div>
      </div>

      <section className="performance-cards">
        <MetricCard
          icon={Target}
          label="Binary accuracy"
          value={`${metrics.binaryAccuracy.toFixed(2)}%`}
          description="BENIGN vs ATTACK"
          tone="blue"
        />
        <MetricCard
          icon={Crosshair}
          label="Attack classifier accuracy"
          value={`${metrics.attackAccuracy.toFixed(2)}%`}
          description="10 output categories"
          tone="green"
        />
        <MetricCard
          icon={CheckCircle2}
          label="Binary F1-score"
          value={`${metrics.binary.f1.toFixed(2)}%`}
          description="Weighted average"
          tone="purple"
        />
        <MetricCard
          icon={Activity}
          label="Attack F1-score"
          value={`${metrics.attack.f1.toFixed(2)}%`}
          description="Macro average"
          tone="orange"
        />
      </section>

      <section className="performance-panel">
        <div className="performance-panel-heading">
          <div>
            <h3>Attack category performance</h3>
            <p>Precision, recall, and F1-score by category</p>
          </div>
        </div>
        <div className="performance-chart">
          <ResponsiveContainer width="100%" height={370}>
            <BarChart
              data={chartData}
              margin={{ top: 12, right: 12, left: 0, bottom: 42 }}
            >
              <CartesianGrid stroke="#26334a" strokeDasharray="3 3" />
              <XAxis
                dataKey="name"
                angle={-25}
                textAnchor="end"
                interval={0}
                height={70}
                tick={{ fill: '#a9b8ce', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: '#a9b8ce', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={value => `${value}%`}
              />
              <Tooltip
                formatter={value => [`${Number(value).toFixed(2)}%`]}
                contentStyle={{
                  background: '#11192a',
                  border: '1px solid #34445e',
                  borderRadius: 8,
                }}
              />
              <Legend />
              <Bar dataKey="precision" name="Precision" fill="#5d8dff" radius={[4, 4, 0, 0]} />
              <Bar dataKey="recall" name="Recall" fill="#21d6a0" radius={[4, 4, 0, 0]} />
              <Bar dataKey="f1" name="F1-score" fill="#b27aff" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="performance-panel">
        <div className="performance-panel-heading">
          <div>
            <h3>Detailed classification report</h3>
            <p>Support is the number of actual test examples in each class.</p>
          </div>
        </div>
        <div className="performance-table-wrap">
          <table className="performance-table">
            <thead>
              <tr>
                <th>Category</th>
                <th>Precision</th>
                <th>Recall</th>
                <th>F1-score</th>
                <th>Test support</th>
                <th>Evaluation</th>
              </tr>
            </thead>
            <tbody>
              {categories.map(item => {
                const limited = item.support < 50
                const weak = item.f1 < 70

                return (
                  <tr key={item.name}>
                    <td>{item.name}</td>
                    <td>{item.precision.toFixed(2)}%</td>
                    <td>{item.recall.toFixed(2)}%</td>
                    <td>
                      <span className={weak ? 'metric-value metric-warning' : 'metric-value'}>
                        {item.f1.toFixed(2)}%
                      </span>
                    </td>
                    <td>{item.support.toLocaleString()}</td>
                    <td>
                      {limited || weak ? (
                        <span className="evaluation-warning">
                          <AlertTriangle size={13} />
                          {limited ? 'Limited samples' : 'Needs improvement'}
                        </span>
                      ) : (
                        <span className="evaluation-good">
                          <CheckCircle2 size={13} />
                          Strong on test set
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="performance-notice performance-warning">
        <AlertTriangle size={20} />
        <div>
          <strong>Areas that need more evaluation</strong>
          <p>
            SQL Injection recall is 25% on only 4 test examples. XSS F1-score
            is 46.91% on 131 examples. Heartbleed and Infiltration also have
            very small test samples. These results are not sufficient to
            establish reliable real-world detection performance for those
            categories.
          </p>
        </div>
      </section>

      <footer className="performance-footer">
        CyberGuard · CICIDS2017 · Held-out evaluation metrics
      </footer>
    </div>
  )
}

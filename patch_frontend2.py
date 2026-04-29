import re
with open("frontend/pages/items/[id].js", "r") as f:
    content = f.read()

stop_func = """  const stopAnalysis = async () => {
    try {
      await axios.post(`${API_BASE_URL}/api/items/${id}/stop`);
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  const exportBrief = async () => {"""

content = content.replace("  const exportBrief = async () => {", stop_func)

button_html = """            <span
              className={`px-3 py-1 rounded-full text-xs font-bold ${
                data.status === "done"
                  ? "bg-emerald-100 text-emerald-700"
                  : data.status === "stopped"
                  ? "bg-slate-100 text-slate-700"
                  : "bg-amber-100 text-amber-700"
              }`}
            >
              {data.status === "done" ? "Analysis Complete" : data.status === "stopped" ? "Analysis Stopped" : "Analysis Running"}
            </span>
            {data.status === "pending" && (
              <button
                onClick={stopAnalysis}
                className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded-full text-xs font-bold transition-colors"
              >
                Stop Analysis
              </button>
            )}
            <span"""

content = content.replace("""            <span
              className={`px-3 py-1 rounded-full text-xs font-bold ${
                data.status === "done"
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-amber-100 text-amber-700"
              }`}
            >
              {data.status === "done" ? "Analysis Complete" : "Analysis Running"}
            </span>
            <span""", button_html)

with open("frontend/pages/items/[id].js", "w") as f:
    f.write(content)

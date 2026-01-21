import newsData from '../data/news.json';

export default function Home() {
  return (
    <main className="min-h-screen p-8 bg-gray-50 text-gray-900">
      <div className="max-w-4xl mx-auto mb-10">
        <h1 className="text-4xl font-bold mb-2">AI Daily Insight</h1>
        <p className="text-gray-500">AI 每日情报站</p>
      </div>

      <div className="max-w-4xl mx-auto space-y-12">
        {newsData.map((day) => (
          <div key={day.date} className="border-l-4 border-black pl-6">
            <div className="mb-6">
              <h2 className="text-2xl font-bold mb-2">{day.date}</h2>
              <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-100">
                <p className="text-gray-700 leading-relaxed">{day.summary}</p>
              </div>
            </div>

            <div className="grid gap-4">
              {day.news.map((item) => (
                <div key={item.id} className="bg-white p-5 rounded-lg shadow-sm hover:shadow-md transition-shadow border border-gray-100">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="bg-gray-100 text-xs px-2 py-1 rounded font-mono text-gray-600">
                      {item.source}
                    </span>
                    {item.tags.map((tag) => (
                      <span key={tag} className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded">
                        #{tag}
                      </span>
                    ))}
                  </div>
                  <a href={item.url} target="_blank" className="text-xl font-bold hover:text-blue-600 block mb-2">
                    {item.title}
                  </a>
                  <p className="text-gray-600 text-sm">{item.summary}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
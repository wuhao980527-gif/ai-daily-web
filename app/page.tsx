"use client";

import newsData from '../data/news.json';
import { useState } from 'react';

// --- 1. 定义视觉风格 ---
const getSourceStyle = (source: string) => {
  switch (source) {
    case 'Product':
      return {
        bgClass: 'bg-gradient-to-br from-blue-500 to-blue-600',
        text: 'text-blue-600',
        icon: '🚀',
        label: 'Product'
      };
    case 'HuggingFace':
      return {
        bgClass: 'bg-gradient-to-br from-yellow-500 to-orange-500',
        text: 'text-orange-600',
        icon: '🤗',
        label: 'HuggingFace'
      };
    case 'GitHub':
      return {
        bgClass: 'bg-gradient-to-br from-gray-700 to-gray-900',
        text: 'text-gray-700',
        icon: '🐙',
        label: 'GitHub'
      };
    case 'Papers':
      return {
        bgClass: 'bg-gradient-to-br from-purple-500 to-indigo-600',
        text: 'text-purple-600',
        icon: '📜',
        label: 'Research'
      };
    default:
      return {
        bgClass: 'bg-gradient-to-br from-emerald-500 to-teal-600',
        text: 'text-emerald-600',
        icon: '⚡',
        label: 'News'
      };
  }
};

// --- 2. 封面组件 ---
const SmartCover = ({ item }: { item: any }) => {
  const [imgError, setImgError] = useState(false);
  const style = getSourceStyle(item.source);

  const getCoverImage = () => {
    if (imgError) return null;

    if (item.source === 'GitHub') {
      const match = item.url.match(/github\.com\/([^/]+\/[^/]+)/);
      if (match) return `https://opengraph.githubassets.com/1/${match[1]}`;
    }

    if (item.source === 'HuggingFace') {
      const match = item.url.match(/huggingface\.co\/(.+)/);
      if (match) {
        return `https://cdn-thumbnails.huggingface.co/social-thumbnails/models/${match[1].replace(/\//g, '--')}.png`;
      }
    }

    return null;
  };

  const coverImg = getCoverImage();

  if (coverImg) {
    return (
      <div className="sm:w-72 h-52 sm:h-auto relative overflow-hidden bg-slate-900 shrink-0 border-r border-slate-800/50">
        <img
          src={coverImg}
          alt={item.title}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700 opacity-95 group-hover:opacity-100"
          onError={() => setImgError(true)}
          loading="lazy"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-slate-900/40 to-transparent"></div>
        <div className="absolute bottom-4 left-4 flex items-center gap-2">
          <span className={`w-10 h-10 ${style.bgClass} rounded-lg flex items-center justify-center text-xl shadow-lg`}>
            {style.icon}
          </span>
          <span className="px-3 py-1 text-xs font-bold text-white bg-black/60 backdrop-blur-md rounded-full border border-white/10 uppercase tracking-wider">
            {style.label}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className={`sm:w-72 h-52 sm:h-auto relative overflow-hidden shrink-0 flex items-center justify-center border-r border-slate-800/50 ${style.bgClass}`}>
      <div className="absolute inset-0 opacity-10"
           style={{
             backgroundImage: 'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)',
             backgroundSize: '24px 24px'
           }}>
      </div>
      <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent"></div>
      <div className="relative z-10 transform group-hover:scale-110 group-hover:-translate-y-2 transition-all duration-500">
        <span className="text-8xl drop-shadow-2xl filter brightness-110">{style.icon}</span>
      </div>
      <div className="absolute bottom-4 left-4">
         <span className="px-3 py-1 text-xs font-bold text-white bg-black/40 backdrop-blur-sm rounded-full border border-white/20 uppercase tracking-wider">
           {style.label}
         </span>
      </div>
    </div>
  );
};

// --- 3. 新闻卡片组件 ---
const NewsCard = ({ item }: { item: any }) => {
  const style = getSourceStyle(item.source);

  return (
    <article
      className="group bg-white rounded-xl border border-gray-200/80 overflow-hidden hover:shadow-xl hover:shadow-blue-900/10 hover:border-blue-300/50 hover:-translate-y-0.5 transition-all duration-300 flex flex-col sm:flex-row"
    >
      <SmartCover item={item} />

      <div className="p-4 sm:p-5 flex flex-col justify-between flex-1 relative">
        <div>
          {/* 标题和热度指标 */}
          <div className="flex justify-between items-start mb-1.5">
            <h3 className="text-lg font-bold text-slate-900 leading-tight group-hover:text-blue-600 transition-colors pr-4 flex-1">
              <a href={item.url} target="_blank" rel="noopener noreferrer" className="before:absolute before:inset-0 sm:before:inset-auto">
                {item.title}
              </a>
            </h3>
            <span className="text-gray-300 group-hover:text-blue-500 transition-all opacity-0 group-hover:opacity-100 transform translate-x-2 group-hover:translate-x-0 text-lg shrink-0">→</span>
          </div>

          {/* 元数据：日期 + 热度 */}
          <div className="flex flex-wrap items-center gap-2.5 mb-2 text-xs">
            {item.date && (
              <span className="flex items-center gap-1 text-slate-500">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <span className="font-medium">{item.date}</span>
              </span>
            )}

            {item.likes !== undefined && item.likes > 0 && (
              <span className={`flex items-center gap-1 font-semibold ${style.text}`}>
                <span className="text-sm">❤️</span>
                <span>{item.likes.toLocaleString()}</span>
              </span>
            )}

            {item.stars !== undefined && item.stars > 0 && (
              <span className={`flex items-center gap-1 font-semibold ${style.text}`}>
                <span className="text-sm">⭐</span>
                <span>{item.stars.toLocaleString()}</span>
              </span>
            )}
          </div>

          <p className="text-slate-600 text-sm leading-relaxed mb-3 line-clamp-3">
            {item.summary}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 mt-auto pt-2">
          {item.tags.map((tag: string) => (
            <span key={tag} className="px-2 py-1 text-[10px] font-semibold text-slate-600 bg-slate-50 rounded-md group-hover:bg-blue-50 group-hover:text-blue-600 transition-all border border-slate-200 group-hover:border-blue-200 uppercase tracking-wide">
              {tag}
            </span>
          ))}
        </div>
      </div>
    </article>
  );
};

export default function Home() {
  const [activeTab, setActiveTab] = useState<'latest' | 'history' | 'github'>('latest');

  // 按日期倒序排序，确保最新的在前面
  const sortedNewsData = [...newsData].sort((a, b) =>
    new Date(b.date).getTime() - new Date(a.date).getTime()
  );

  const latestDay = sortedNewsData[0]; // 最新的一天
  const historyDays = sortedNewsData.slice(1); // 其他所有历史

  const getSourceStats = () => {
    const stats: Record<string, number> = {};
    newsData.forEach(day => {
      day.news.forEach(item => {
        stats[item.source] = (stats[item.source] || 0) + 1;
      });
    });
    return Object.entries(stats).sort((a, b) => b[1] - a[1]);
  };

  const sourceStats = getSourceStats();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-50 text-[#333] font-sans selection:bg-blue-100">

      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-gray-200/50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-cyan-500 rounded-xl flex items-center justify-center text-white text-xl font-bold shadow-lg shadow-blue-500/30">
                <span>AI</span>
              </div>
              <span className="text-xl font-black tracking-tight bg-gradient-to-r from-slate-800 to-slate-600 bg-clip-text text-transparent">Daily Insight</span>
            </div>
          </div>

          {/* 标签导航 */}
          <nav className="flex gap-8 -mb-px">
            <button
              onClick={() => setActiveTab('latest')}
              className={`px-1 py-4 text-sm font-semibold border-b-2 transition-colors ${
                activeTab === 'latest'
                  ? 'text-blue-600 border-blue-600'
                  : 'text-gray-500 border-transparent hover:text-gray-900 hover:border-gray-300'
              }`}
            >
              最新动态
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`px-1 py-4 text-sm font-semibold border-b-2 transition-colors ${
                activeTab === 'history'
                  ? 'text-blue-600 border-blue-600'
                  : 'text-gray-500 border-transparent hover:text-gray-900 hover:border-gray-300'
              }`}
            >
              历史归档
            </button>
            <a
              href="https://github.com/wuhao980527-gif/ai-daily-web"
              target="_blank"
              className={`px-1 py-4 text-sm font-semibold border-b-2 transition-colors ${
                activeTab === 'github'
                  ? 'text-blue-600 border-blue-600'
                  : 'text-gray-500 border-transparent hover:text-gray-900 hover:border-gray-300'
              }`}
              onClick={() => setActiveTab('github')}
            >
              GitHub
            </a>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="flex flex-col lg:flex-row gap-12">

          {/* 左侧：主内容区 */}
          <div className="w-full lg:w-3/4">

            {/* 最新动态页 */}
            {activeTab === 'latest' && latestDay && (
              <section className="animate-in fade-in slide-in-from-bottom-4 duration-700">
                <div className="flex items-center gap-3 mb-6">
                  <h2 className="text-4xl font-black text-slate-800 tracking-tight">{latestDay.date}</h2>
                  <span className="bg-gradient-to-r from-red-500 to-pink-500 text-white text-xs font-bold px-3 py-1 rounded-full shadow-lg shadow-red-500/30 animate-pulse">
                    LIVE
                  </span>
                </div>

                {/* 每日总结 */}
                <div className="bg-gradient-to-r from-blue-50 to-indigo-50 p-6 rounded-2xl text-sm border-l-4 border-blue-500 shadow-sm mb-6">
                  <div className="flex gap-4 items-start">
                    <span className="text-3xl bg-white w-12 h-12 rounded-xl flex items-center justify-center shrink-0 shadow-sm">💡</span>
                    <div>
                      <h3 className="font-bold text-slate-800 mb-2">今日要点</h3>
                      <p className="text-slate-700 leading-relaxed">{latestDay.summary}</p>
                    </div>
                  </div>
                </div>

                {/* 新闻列表 */}
                <div className="space-y-6">
                  {latestDay.news.map((item) => (
                    <NewsCard key={item.id} item={item} />
                  ))}
                </div>
              </section>
            )}

            {/* 历史归档页 */}
            {activeTab === 'history' && (
              <section className="animate-in fade-in slide-in-from-bottom-4 duration-700">
                <div className="flex items-center gap-4 mb-6">
                  <div className="h-px flex-1 bg-gradient-to-r from-transparent via-gray-300 to-transparent"></div>
                  <h2 className="text-3xl font-black text-slate-600 tracking-tight flex items-center gap-2">
                    <span className="text-gray-400">📚</span>
                    历史归档
                  </h2>
                  <div className="h-px flex-1 bg-gradient-to-r from-transparent via-gray-300 to-transparent"></div>
                </div>

                <div className="space-y-4">
                  {historyDays.map((day) => (
                    <details key={day.date} className="group/detail bg-white rounded-xl border border-gray-200/80 overflow-hidden open:shadow-lg open:border-blue-200 transition-all duration-300">
                      <summary className="flex items-center justify-between p-5 cursor-pointer bg-gradient-to-r from-white to-slate-50/50 hover:from-blue-50/50 hover:to-indigo-50/30 transition-all select-none list-none group-hover/detail:shadow-inner">
                        <div className="flex items-center gap-4">
                          <span className="text-lg font-bold text-slate-500 group-open/detail:text-blue-600 transition-colors min-w-[110px]">{day.date}</span>
                          <div className="h-6 w-px bg-gray-200"></div>
                          <span className="text-sm text-gray-500 line-clamp-1 max-w-md">{day.summary}</span>
                        </div>
                        <div className="w-9 h-9 rounded-xl bg-slate-100 flex items-center justify-center text-slate-400 group-open/detail:rotate-180 group-open/detail:bg-blue-100 group-open/detail:text-blue-600 transition-all duration-300 shadow-sm">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                      </summary>
                      <div className="p-6 border-t border-gray-100 bg-slate-50/30 animate-in fade-in zoom-in-95 duration-200 space-y-6">
                        {day.news.map((item) => (
                          <NewsCard key={item.id} item={item} />
                        ))}
                      </div>
                    </details>
                  ))}
                </div>
              </section>
            )}

            {/* GitHub 页面（重定向提示） */}
            {activeTab === 'github' && (
              <section className="animate-in fade-in slide-in-from-bottom-4 duration-700">
                <div className="bg-white rounded-2xl border border-gray-200/80 p-12 text-center">
                  <div className="text-6xl mb-6">🐙</div>
                  <h2 className="text-3xl font-black text-slate-800 mb-4">正在跳转到 GitHub...</h2>
                  <p className="text-slate-600 mb-8">查看项目源代码、提交 Issue 或参与贡献</p>
                  <a
                    href="https://github.com/wuhao980527-gif/ai-daily-web"
                    target="_blank"
                    className="inline-block px-6 py-3 bg-gradient-to-r from-gray-800 to-gray-900 text-white font-bold rounded-lg hover:shadow-lg transition-all"
                  >
                    访问 GitHub 仓库 →
                  </a>
                </div>
              </section>
            )}

          </div>

          {/* 右侧：侧边栏 */}
          <aside className="hidden lg:block w-1/4 space-y-6 sticky top-24 h-fit">
            {/* 数据源统计 */}
            <div className="bg-white rounded-2xl border border-gray-200/80 p-6 shadow-sm hover:shadow-md transition-shadow">
              <h3 className="font-bold text-slate-800 mb-5 flex items-center gap-2">
                <span className="w-1 h-5 bg-gradient-to-b from-blue-600 to-cyan-500 rounded-full"></span>
                数据来源
              </h3>
              <div className="space-y-3">
                {sourceStats.map(([source, count]) => {
                   const style = getSourceStyle(source);
                   return (
                    <div key={source} className="flex items-center justify-between text-sm group/stat cursor-default">
                      <span className="text-slate-600 flex items-center gap-3">
                        <span className={`w-9 h-9 rounded-lg flex items-center justify-center text-sm shadow-sm ${style.bgClass} text-white`}>
                          {style.icon}
                        </span>
                        <span className="font-medium group-hover/stat:text-blue-600 transition-colors">{source}</span>
                      </span>
                      <span className="font-mono text-xs font-bold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-lg group-hover/stat:bg-blue-50 group-hover/stat:text-blue-600 transition-colors">{count}</span>
                    </div>
                   )
                })}
              </div>
            </div>

            {/* 项目信息 */}
            <div className="group/card relative overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-2xl p-6 text-center shadow-xl">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 to-purple-600/20 opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"></div>
              <div className="relative z-10">
                <div className="text-5xl mb-3 transform group-hover/card:-translate-y-1 transition-transform duration-300">🤖</div>
                <h3 className="font-bold text-xl text-white mb-2">AI Daily Insight</h3>
                <p className="text-slate-300 text-xs leading-relaxed mb-6">
                  全自动 AI 驱动的情报聚合站<br/>
                  <span className="text-slate-400">Python Agent · LangGraph · Next.js</span>
                </p>
                <div className="flex justify-center items-center gap-3">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  <span className="text-xs text-emerald-400 font-mono uppercase tracking-wider">System Online</span>
                </div>
              </div>
            </div>
          </aside>

        </div>
      </main>

      {/* Footer */}
      <footer className="mt-20 py-8 border-t border-gray-200 bg-white/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-sm text-gray-500">
          <p>© 2026 AI Daily Insight · Powered by LangGraph & Groq</p>
          <p className="mt-2 text-xs">每日 UTC 01:00 自动更新</p>
        </div>
      </footer>
    </div>
  );
}

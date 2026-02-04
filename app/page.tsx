"use client";

import newsData from '../data/news.json';
import { useState } from 'react';

// --- 1. 定义更高级的视觉风格 (科技网格 + 赛博配色) ---
const getSourceStyle = (source: string) => {
  switch (source) {
    case 'Product':
      return {
        bgClass: 'bg-gradient-to-br from-blue-500 to-blue-600',
        gradient: 'from-blue-600/20 via-blue-900/40 to-slate-900',
        border: 'border-blue-500/30',
        text: 'text-blue-400',
        icon: '🚀',
        label: 'Product'
      };
    case 'HuggingFace':
      return {
        bgClass: 'bg-gradient-to-br from-yellow-500 to-orange-500',
        gradient: 'from-amber-500/20 via-yellow-900/40 to-slate-900',
        border: 'border-amber-500/30',
        text: 'text-amber-400',
        icon: '🤗',
        label: 'HuggingFace'
      };
    case 'GitHub':
      return {
        bgClass: 'bg-gradient-to-br from-gray-700 to-gray-900',
        gradient: 'from-gray-700/20 via-gray-900/40 to-black',
        border: 'border-gray-600/30',
        text: 'text-gray-300',
        icon: '🐙',
        label: 'GitHub'
      };
    case 'Papers':
      return {
        bgClass: 'bg-gradient-to-br from-purple-500 to-indigo-600',
        gradient: 'from-purple-600/20 via-indigo-900/40 to-slate-900',
        border: 'border-purple-500/30',
        text: 'text-purple-400',
        icon: '📜',
        label: 'Research'
      };
    default:
      return {
        bgClass: 'bg-gradient-to-br from-emerald-500 to-teal-600',
        gradient: 'from-emerald-600/20 via-teal-900/40 to-slate-900',
        border: 'border-emerald-500/30',
        text: 'text-emerald-400',
        icon: '⚡',
        label: 'News'
      };
  }
};

// --- 2. 增强的封面组件（支持多种图片源） ---
const SmartCover = ({ item }: { item: any }) => {
  const [imgError, setImgError] = useState(false);
  const style = getSourceStyle(item.source);

  // 获取不同来源的封面图
  const getCoverImage = () => {
    if (imgError) return null;

    // GitHub: 使用 OG 图
    if (item.source === 'GitHub') {
      const match = item.url.match(/github\.com\/([^/]+\/[^/]+)/);
      if (match) {
        return `https://opengraph.githubassets.com/1/${match[1]}`;
      }
    }

    // HuggingFace: 使用模型卡片图
    if (item.source === 'HuggingFace') {
      const match = item.url.match(/huggingface\.co\/(.+)/);
      if (match) {
        // 尝试获取模型的预览图
        return `https://cdn-thumbnails.huggingface.co/social-thumbnails/models/${match[1].replace(/\//g, '--')}.png`;
      }
    }

    // Papers: 使用 Arxiv 图标或占位符
    if (item.source === 'Papers') {
      // 可以返回一个学术风格的背景
      return null;
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

  // 默认渲染：硬核科技风卡片
  return (
    <div className={`sm:w-72 h-52 sm:h-auto relative overflow-hidden shrink-0 flex items-center justify-center border-r border-slate-800/50 ${style.bgClass}`}>
      {/* 科技网格纹理 */}
      <div className="absolute inset-0 opacity-10"
           style={{
             backgroundImage: 'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)',
             backgroundSize: '24px 24px'
           }}>
      </div>
      <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent"></div>

      {/* 巨型图标 */}
      <div className="relative z-10 transform group-hover:scale-110 group-hover:-translate-y-2 transition-all duration-500">
        <span className="text-8xl drop-shadow-2xl filter brightness-110">{style.icon}</span>
      </div>

      {/* 底部标签 */}
      <div className="absolute bottom-4 left-4">
         <span className="px-3 py-1 text-xs font-bold text-white bg-black/40 backdrop-blur-sm rounded-full border border-white/20 uppercase tracking-wider">
           {style.label}
         </span>
      </div>
    </div>
  );
};

// 统计逻辑
const getSourceStats = () => {
  const stats: Record<string, number> = {};
  newsData.forEach(day => {
    day.news.forEach(item => {
      stats[item.source] = (stats[item.source] || 0) + 1;
    });
  });
  return Object.entries(stats).sort((a, b) => b[1] - a[1]);
};

export default function Home() {
  const sourceStats = getSourceStats();
  const latestDay = newsData[0];
  const historyDays = newsData.slice(1);

  const scrollToHistory = () => {
    const historySection = document.getElementById('history-section');
    if (historySection) {
      historySection.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // 新闻卡片组件
  const NewsCard = ({ item }: { item: any }) => (
    <article
      className="group bg-white rounded-2xl border border-gray-200/80 overflow-hidden hover:shadow-2xl hover:shadow-blue-900/10 hover:border-blue-300/50 hover:-translate-y-1 transition-all duration-300 flex flex-col sm:flex-row"
    >
      <SmartCover item={item} />

      <div className="p-6 sm:p-8 flex flex-col justify-between flex-1 relative">
        <div>
          <div className="flex justify-between items-start mb-3">
            <h3 className="text-xl font-bold text-slate-900 leading-snug group-hover:text-blue-600 transition-colors pr-4">
              <a href={item.url} target="_blank" rel="noopener noreferrer" className="before:absolute before:inset-0 sm:before:inset-auto">
                {item.title}
              </a>
            </h3>
            <span className="text-gray-300 group-hover:text-blue-500 transition-all opacity-0 group-hover:opacity-100 transform translate-x-2 group-hover:translate-x-0 text-xl">→</span>
          </div>
          <p className="text-slate-600 text-[15px] leading-relaxed mb-4">
            {item.summary}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 mt-auto pt-4">
          {item.tags.map((tag: string) => (
            <span key={tag} className="px-3 py-1.5 text-xs font-semibold text-slate-600 bg-slate-50 rounded-lg group-hover:bg-blue-50 group-hover:text-blue-600 transition-all border border-slate-200 group-hover:border-blue-200 uppercase tracking-wide">
              {tag}
            </span>
          ))}
        </div>
      </div>
    </article>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-50 text-[#333] font-sans selection:bg-blue-100">

      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-gray-200/50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-cyan-500 rounded-xl flex items-center justify-center text-white text-xl font-bold shadow-lg shadow-blue-500/30">
              <span>AI</span>
            </div>
            <span className="text-xl font-black tracking-tight bg-gradient-to-r from-slate-800 to-slate-600 bg-clip-text text-transparent">Daily Insight</span>
          </div>
          <nav className="hidden md:flex space-x-8 text-sm font-semibold text-gray-600">
            <button onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} className="text-blue-600 border-b-2 border-blue-600 px-1 h-16 flex items-center hover:text-blue-700 transition-colors">
              最新动态
            </button>
            <button onClick={scrollToHistory} className="hover:text-gray-900 transition-colors px-1 h-16 flex items-center">
              历史归档
            </button>
            <a href="https://github.com/wuhao980527-gif/ai-daily-web" target="_blank" className="hover:text-gray-900 transition-colors px-1 h-16 flex items-center">GitHub</a>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="flex flex-col lg:flex-row gap-12">

          {/* 左侧：新闻流 */}
          <div className="w-full lg:w-3/4 space-y-12">

            {/* 最新动态区域 */}
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

              {/* 最新新闻列表 */}
              <div className="space-y-6">
                {latestDay.news.map((item) => (
                  <NewsCard key={item.id} item={item} />
                ))}
              </div>
            </section>

            {/* 历史归档区域 */}
            <section id="history-section" className="pt-12">
              <div className="flex items-center gap-4 mb-6">
                <div className="h-px flex-1 bg-gradient-to-r from-transparent via-gray-300 to-transparent"></div>
                <h2 className="text-2xl font-black text-slate-600 tracking-tight flex items-center gap-2">
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

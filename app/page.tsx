"use client";

import newsData from '../data/news.json';
import { useState } from 'react';

// --- 1. 定义更高级的视觉风格 (科技网格 + 赛博配色) ---
const getSourceStyle = (source: string) => {
  switch (source) {
    case 'Product': 
      return { 
        // 蓝色系：深邃科技蓝
        bgClass: 'bg-slate-900',
        gradient: 'from-blue-600/20 via-blue-900/40 to-slate-900',
        border: 'border-blue-500/30',
        text: 'text-blue-400',
        icon: '🚀', 
        label: 'Product Release' 
      };
    case 'HuggingFace': 
      return { 
        // 黄色系：黑金风格
        bgClass: 'bg-slate-900',
        gradient: 'from-amber-500/20 via-yellow-900/40 to-slate-900',
        border: 'border-amber-500/30',
        text: 'text-amber-400',
        icon: '🤗', 
        label: 'HuggingFace' 
      };
    case 'GitHub': 
      return { 
        // 黑色系：极客灰
        bgClass: 'bg-slate-950',
        gradient: 'from-gray-700/20 via-gray-900/40 to-black',
        border: 'border-gray-600/30',
        text: 'text-gray-300',
        icon: '🐙', // 统一用章鱼
        label: 'Open Source' 
      };
    case 'Papers': 
      return { 
        // 紫色系：学术紫
        bgClass: 'bg-slate-900',
        gradient: 'from-purple-600/20 via-indigo-900/40 to-slate-900',
        border: 'border-purple-500/30',
        text: 'text-purple-400',
        icon: '📜', 
        label: 'Research' 
      };
    default: 
      return { 
        bgClass: 'bg-slate-900',
        gradient: 'from-emerald-600/20 via-teal-900/40 to-slate-900',
        border: 'border-emerald-500/30',
        text: 'text-emerald-400',
        icon: '⚡', 
        label: 'News' 
      };
  }
};

// --- 2. 智能封面组件 (纯CSS画出科技感) ---
const SmartCover = ({ item }: { item: any }) => {
  const [imgError, setImgError] = useState(false);
  const style = getSourceStyle(item.source);

  // GitHub 优先尝试加载官方 OG 图
  const showImage = item.source === 'GitHub' && !imgError;
  const getGithubUrl = (url: string) => {
    const match = url.match(/github\.com\/([^/]+\/[^/]+)/);
    return match ? `https://opengraph.githubassets.com/1/${match[1]}` : null;
  };
  const imgUrl = showImage ? getGithubUrl(item.url) : null;

  if (imgUrl) {
    return (
      <div className="sm:w-64 h-48 sm:h-auto relative overflow-hidden bg-slate-900 shrink-0 border-r border-slate-800">
        <img 
          src={imgUrl} 
          alt={item.title}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700 opacity-90 group-hover:opacity-100"
          onError={() => setImgError(true)}
          loading="lazy"
        />
        <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-t from-slate-900/80 to-transparent"></div>
        <div className="absolute bottom-3 left-3">
           <span className="px-2 py-0.5 text-[10px] font-mono font-bold text-white bg-black/60 backdrop-blur-md rounded border border-white/10">
             GITHUB REPO
           </span>
        </div>
      </div>
    );
  }

  // 默认渲染：硬核科技风卡片
  return (
    <div className={`sm:w-64 h-48 sm:h-auto relative overflow-hidden shrink-0 flex items-center justify-center ${style.bgClass} border-r ${style.border}`}>
      
      {/* 1. 动态光晕背景 */}
      <div className={`absolute inset-0 bg-gradient-to-br ${style.gradient} opacity-80`}></div>
      
      {/* 2. 科技网格纹理 (CSS Pattern) */}
      <div className="absolute inset-0 opacity-20" 
           style={{
             backgroundImage: 'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)',
             backgroundSize: '20px 20px'
           }}>
      </div>
      <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent"></div>

      {/* 3. 巨型图标 (带浮动动画) */}
      <div className="relative z-10 transform group-hover:scale-110 group-hover:-translate-y-1 transition-all duration-500">
        <span className="text-7xl drop-shadow-2xl filter saturate-150">{style.icon}</span>
      </div>

      {/* 4. 装饰性文字 */}
      <div className="absolute top-3 right-3 opacity-30">
        <svg width="40" height="40" viewBox="0 0 100 100" className={style.text}>
           <circle cx="50" cy="50" r="40" stroke="currentColor" strokeWidth="2" fill="none" strokeDasharray="10 5" />
        </svg>
      </div>

      {/* 5. 底部标签 */}
      <div className="absolute bottom-3 left-3">
         <span className={`px-2 py-0.5 text-[10px] font-mono font-bold bg-black/40 backdrop-blur-sm rounded border border-white/10 uppercase tracking-wider ${style.text}`}>
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

  const scrollToHistory = () => {
    const historySection = document.getElementById('history-section');
    if (historySection) {
      historySection.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-[#333] font-sans selection:bg-blue-100">
      
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-gray-200 shadow-sm transition-all supports-[backdrop-filter]:bg-white/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-slate-900 rounded-lg flex items-center justify-center text-white text-lg font-bold shadow-lg shadow-blue-900/20">
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">AI</span>
            </div>
            <span className="text-xl font-extrabold tracking-tight text-slate-800">Daily Insight</span>
          </div>
          <nav className="hidden md:flex space-x-8 text-sm font-semibold text-gray-500">
            <button onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} className="text-blue-600 border-b-2 border-blue-600 px-1 h-16 flex items-center">
              最新动态
            </button>
            {/* 修复：点击滚动到历史区 */}
            <button onClick={scrollToHistory} className="hover:text-gray-900 transition-colors px-1 h-16 flex items-center">
              历史归档
            </button>
            <a href="#" className="hover:text-gray-900 transition-colors px-1 h-16 flex items-center">关于项目</a>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="flex flex-col lg:flex-row gap-12">
          
          {/* 左侧：新闻流 */}
          <div className="w-full lg:w-3/4 space-y-12">
            {newsData.map((day, index) => {
              const isLatest = index === 0;

              const ContentList = () => (
                <div className="space-y-6 mt-6">
                   {/* 当日摘要 */}
                   <div className="bg-white p-5 rounded-xl text-sm border-l-4 border-blue-500 shadow-sm flex gap-4 items-start">
                      <span className="text-xl bg-blue-50 w-8 h-8 rounded-full flex items-center justify-center shrink-0">💡</span>
                      <span className="text-slate-600 leading-relaxed pt-1">{day.summary}</span>
                   </div>

                   {day.news.map((item) => (
                      <article 
                        key={item.id} 
                        className="group bg-white rounded-2xl border border-gray-200 overflow-hidden hover:shadow-xl hover:shadow-blue-900/5 hover:border-blue-200 transition-all duration-300 flex flex-col sm:flex-row"
                      >
                        {/* 🌟 智能封面 (科技风) */}
                        <SmartCover item={item} />

                        {/* 文字内容 */}
                        <div className="p-6 flex flex-col justify-between flex-1 relative">
                          <div>
                            <div className="flex justify-between items-start mb-2">
                              <h3 className="text-lg font-bold text-slate-900 leading-snug group-hover:text-blue-600 transition-colors pr-4">
                                <a href={item.url} target="_blank" rel="noopener noreferrer" className="before:absolute before:inset-0 sm:before:inset-auto">
                                  {item.title}
                                </a>
                              </h3>
                              <span className="text-gray-300 group-hover:text-blue-500 transition-colors opacity-0 group-hover:opacity-100">↗</span>
                            </div>
                            <p className="text-slate-500 text-sm leading-relaxed line-clamp-2 mb-4">
                              {item.summary}
                            </p>
                          </div>
                          
                          <div className="flex flex-wrap items-center gap-2 mt-auto">
                            {item.tags.map(tag => (
                              <span key={tag} className="px-2.5 py-1 text-[11px] font-semibold text-slate-500 bg-slate-100 rounded-full group-hover:bg-blue-50 group-hover:text-blue-600 transition-colors border border-transparent group-hover:border-blue-100 uppercase tracking-wide">
                                {tag}
                              </span>
                            ))}
                          </div>
                        </div>
                      </article>
                   ))}
                </div>
              );

              if (isLatest) {
                return (
                  <div key={day.date} className="animate-in fade-in slide-in-from-bottom-4 duration-700">
                    <div className="flex items-center gap-3 mb-4">
                      <h2 className="text-3xl font-black text-slate-800 tracking-tighter">{day.date}</h2>
                      <span className="bg-red-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full shadow-red-500/30 shadow-md animate-pulse">LIVE</span>
                    </div>
                    <div className="h-px w-full bg-gradient-to-r from-gray-200 to-transparent mb-8"></div>
                    <ContentList />
                  </div>
                );
              }

              return (
                // 历史归档区 ID
                <div id={index === 1 ? "history-section" : undefined} key={day.date}>
                  <details className="group/detail bg-white rounded-2xl border border-gray-200 overflow-hidden open:shadow-lg open:border-blue-100 transition-all duration-300 mb-4">
                    <summary className="flex items-center justify-between p-6 cursor-pointer bg-white hover:bg-gray-50 transition-colors select-none list-none">
                      <div className="flex items-center gap-4">
                        <span className="text-xl font-bold text-slate-400 group-open/detail:text-blue-600 transition-colors">{day.date}</span>
                        <span className="text-sm text-gray-400 line-clamp-1 opacity-70 group-hover/detail:opacity-100">{day.summary.slice(0, 30)}...</span>
                      </div>
                      <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-gray-400 group-open/detail:rotate-180 group-open/detail:bg-blue-50 group-open/detail:text-blue-600 transition-all">
                        ▼
                      </div>
                    </summary>
                    <div className="p-6 border-t border-gray-100 bg-slate-50/30 animate-in fade-in zoom-in-95 duration-200">
                      <ContentList />
                    </div>
                  </details>
                </div>
              );
            })}
          </div>

          {/* 右侧：侧边栏 (已修复图标一致性) */}
          <aside className="hidden lg:block w-1/4 space-y-8 sticky top-24 h-fit">
            <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
              <h3 className="font-bold text-slate-800 mb-5 flex items-center gap-2">
                <span className="w-1 h-4 bg-blue-600 rounded-full"></span>
                情报来源
              </h3>
              <div className="space-y-3">
                {sourceStats.map(([source, count]) => {
                   const style = getSourceStyle(source);
                   return (
                    <div key={source} className="flex items-center justify-between text-sm group cursor-default">
                      <span className="text-slate-600 flex items-center gap-3">
                        {/* 这里的图标和样式现在与卡片完全一致 */}
                        <span className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm shadow-sm border ${style.bgClass} ${style.border} ${style.text}`}>
                          {style.icon}
                        </span>
                        <span className="font-medium group-hover:text-blue-600 transition-colors">{source}</span>
                      </span>
                      <span className="font-mono text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full group-hover:bg-blue-50 group-hover:text-blue-600 transition-colors">{count}</span>
                    </div>
                   )
                })}
              </div>
            </div>

            <div className="group relative overflow-hidden bg-slate-900 rounded-2xl p-6 text-center shadow-xl shadow-slate-900/10">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 to-purple-600/20 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
              <div className="relative z-10">
                <div className="text-4xl mb-3 transform group-hover:-translate-y-1 transition-transform duration-300">🤖</div>
                <h3 className="font-bold text-lg text-white mb-2">AI Daily Insight</h3>
                <p className="text-slate-400 text-xs leading-relaxed mb-6">
                  全自动 AI 驱动的情报聚合站。<br/>
                  Python 抓取 · Agent 清洗 · Next.js 呈现
                </p>
                <div className="flex justify-center gap-3">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                  </span>
                  <span className="text-[10px] text-green-400 font-mono uppercase tracking-wider">System Online</span>
                </div>
              </div>
            </div>
          </aside>

        </div>
      </main>
    </div>
  );
}
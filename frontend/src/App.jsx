import { useState } from "react";
import LiveAPIDemo from "./components/LiveAPIDemo";
import Header from "./components/Header";
import Footer from "./components/Footer";
import "./App.css";

function App() {
  const [currentPage, setCurrentPage] = useState("home");

  const navigateTo = (page) => {
    setCurrentPage(page);
    window.scrollTo(0, 0);
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Header onNavigate={navigateTo} />
      
      <main className="flex-grow">
        {currentPage === "home" ? (
          <div className="container mx-auto px-4 py-16 text-center">
            <h1 className="text-5xl font-extrabold mb-6 bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600">
              AI Voice Mock Interview
            </h1>
            <p className="text-xl mb-10 max-w-2xl mx-auto text-gray-600 dark:text-gray-300">
              Luyện phỏng vấn bằng giọng nói với trí tuệ nhân tạo – tăng cường tự tin
              trước khi bước vào thị trường lao động. Trải nghiệm phỏng vấn thực tế ngay tại nhà.
            </p>
            <button
              onClick={() => navigateTo('interview')}
              className="inline-block bg-blue-600 text-white py-4 px-10 rounded-full text-lg font-semibold hover:bg-blue-700 transition-all transform hover:scale-105 shadow-lg"
            >
              Bắt đầu luyện tập
            </button>
            
            <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-8 text-left">
              <div className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-md border border-gray-100 dark:border-gray-700">
                <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center mb-4">
                  <span className="text-2xl">🎙️</span>
                </div>
                <h3 className="text-xl font-bold mb-2">Giọng nói tự nhiên</h3>
                <p className="text-gray-600 dark:text-gray-400">Tương tác trực tiếp bằng giọng nói, giống như một buổi phỏng vấn thật.</p>
              </div>
              <div className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-md border border-gray-100 dark:border-gray-700">
                <div className="w-12 h-12 bg-indigo-100 dark:bg-indigo-900 rounded-lg flex items-center justify-center mb-4">
                  <span className="text-2xl">⚡</span>
                </div>
                <h3 className="text-xl font-bold mb-2">Phản hồi tức thì</h3>
                <p className="text-gray-600 dark:text-gray-400">Nhận phản hồi và gợi ý ngay lập tức từ trí tuệ nhân tạo.</p>
              </div>
              <div className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-md border border-gray-100 dark:border-gray-700">
                <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900 rounded-lg flex items-center justify-center mb-4">
                  <span className="text-2xl">📈</span>
                </div>
                <h3 className="text-xl font-bold mb-2">Cải thiện kỹ năng</h3>
                <p className="text-gray-600 dark:text-gray-400">Nâng cao kỹ năng giao tiếp và tự tin khi đối mặt với nhà tuyển dụng.</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="py-8">
            <LiveAPIDemo />
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}

export default App;

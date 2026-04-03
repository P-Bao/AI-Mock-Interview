// Header chung với logo và điều hướng
export default function Header({ onNavigate }) {
  return (
    <header className="w-full bg-white dark:bg-gray-800 shadow sticky top-0 z-50">
      <div className="w-full px-8 py-4 flex justify-between items-center max-w-full">
        <button 
          onClick={() => onNavigate('home')} 
          className="text-xl font-bold cursor-pointer hover:opacity-80 transition"
        >
          AI Mock Interview
        </button>
        <nav>
          <button 
            onClick={() => onNavigate('home')} 
            className="mr-4 hover:underline cursor-pointer"
          >
            Trang chủ
          </button>
          <button 
            onClick={() => onNavigate('interview')} 
            className="hover:underline cursor-pointer"
          >
            Phỏng vấn
          </button>
        </nav>
      </div>
    </header>
  );
}

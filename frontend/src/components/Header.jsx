// Header chung với logo và điều hướng
export default function Header({ onNavigate }) {
  return (
    <header className="w-full bg-white dark:bg-gray-800 shadow sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4 flex justify-between items-center">
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

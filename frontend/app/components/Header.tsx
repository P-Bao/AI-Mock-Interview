import Link from "next/link";

// Header chung với logo và điều hướng
export default function Header() {
  return (
    <header className="w-full bg-white dark:bg-gray-800 shadow">
      <div className="container mx-auto px-4 py-4 flex justify-between items-center">
        <Link href="/" className="text-xl font-bold">
          AI Mock Interview
        </Link>
        <nav>
          <Link href="/" className="mr-4 hover:underline">
            Trang chủ
          </Link>
          <Link href="/interview" className="hover:underline">
            Phỏng vấn
          </Link>
        </nav>
      </div>
    </header>
  );
}

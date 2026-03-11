import Link from "next/link";

// Trang chủ giới thiệu sản phẩm, có nút dẫn tới buổi phỏng vấn
export default function Home() {
  return (
    <main className="container mx-auto px-4 py-16 text-center">
      <h1 className="text-4xl font-extrabold mb-4">
        AI Voice Mock Interview
      </h1>
      <p className="text-lg mb-8">
        Luyện phỏng vấn bằng giọng nói với trí tuệ nhân tạo – tăng cường tự tin
        trước khi bước vào thị trường lao động.
      </p>
      <Link
        href="/interview"
        className="inline-block bg-blue-600 text-white py-3 px-6 rounded hover:bg-blue-700 transition"
      >
        Bắt đầu luyện tập
      </Link>
    </main>
  );
}

// Footer chung hiển thị thông tin bản quyền
export default function Footer() {
  return (
    <footer className="w-full bg-gray-100 dark:bg-gray-900 py-6 mt-auto">
      <div className="container mx-auto text-center text-sm text-gray-600 dark:text-gray-400 px-4">
        © {new Date().getFullYear()} AI Mock Interview. Tất cả các quyền được bảo lưu.
      </div>
    </footer>
  );
}

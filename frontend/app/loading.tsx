/**
 * Loading state shown while the landing page or game page is loading.
 */
export default function Loading() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-6">
      <div className="glass rounded-2xl p-8 max-w-md w-full space-y-6">
        <div className="flex justify-center">
          <div className="w-12 h-12 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
        </div>
        <div className="space-y-3">
          <div className="skeleton h-4 w-3/4 mx-auto" />
          <div className="skeleton h-4 w-1/2 mx-auto" />
        </div>
        <p className="text-center text-sm text-gray-500 animate-pulse">
          Loading...
        </p>
      </div>
    </div>
  );
}

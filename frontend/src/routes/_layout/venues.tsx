import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { Suspense } from "react"

import { VenuesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import PendingVenues from "@/components/Pending/PendingVenues"
import AddVenue from "@/components/Venues/AddVenue"
import { columns, type VenueTableData } from "@/components/Venues/columns"
import useAuth from "@/hooks/useAuth"

function getVenuesQueryOptions() {
  return {
    queryFn: async () =>
      (await VenuesService.readVenues({ query: { skip: 0, limit: 100 } })).data,
    queryKey: ["venues"],
  }
}

export const Route = createFileRoute("/_layout/venues")({
  component: Venues,
  head: () => ({
    meta: [
      {
        title: "Venues - Campus Space Booking",
      },
    ],
  }),
})

function VenuesTableContent() {
  const { user: currentUser } = useAuth()
  const { data: venues } = useSuspenseQuery(getVenuesQueryOptions())

  const canManage = Boolean(
    currentUser?.is_superuser || currentUser?.role === "admin",
  )

  const tableData: VenueTableData[] = venues.data.map((venue) => ({
    ...venue,
    canManage,
  }))

  if (venues.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Search className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No venues yet</h3>
        <p className="text-muted-foreground">
          {canManage
            ? "Add your first venue to start accepting bookings"
            : "Ask an administrator to add venues"}
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={tableData} />
}

function VenuesTable() {
  return (
    <Suspense fallback={<PendingVenues />}>
      <VenuesTableContent />
    </Suspense>
  )
}

function Venues() {
  const { user: currentUser } = useAuth()
  const canManage = Boolean(
    currentUser?.is_superuser || currentUser?.role === "admin",
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Venues</h1>
          <p className="text-muted-foreground">
            Browse bookable campus spaces
          </p>
        </div>
        {canManage && <AddVenue />}
      </div>
      <VenuesTable />
    </div>
  )
}

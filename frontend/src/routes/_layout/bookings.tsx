import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { Suspense } from "react"

import {
  type BookingStatus,
  BookingsService,
  VenuesService,
} from "@/client"
import AddBooking from "@/components/Bookings/AddBooking"
import {
  type BookingTableData,
  columns,
} from "@/components/Bookings/columns"
import { DataTable } from "@/components/Common/DataTable"
import PendingBookings from "@/components/Pending/PendingBookings"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"

type StatusFilter = BookingStatus | "all"

const FILTERS: StatusFilter[] = [
  "all",
  "pending",
  "approved",
  "rejected",
  "cancelled",
]

function getBookingsQueryOptions(status: StatusFilter) {
  return {
    queryFn: async () =>
      (
        await BookingsService.readBookings({
          query: {
            skip: 0,
            limit: 100,
            status: status === "all" ? undefined : status,
          },
        })
      ).data,
    queryKey: ["bookings", status],
  }
}

function getVenuesQueryOptions() {
  return {
    queryFn: async () =>
      (await VenuesService.readVenues({ query: { skip: 0, limit: 100 } })).data,
    queryKey: ["venues"],
  }
}

export const Route = createFileRoute("/_layout/bookings")({
  component: Bookings,
  head: () => ({
    meta: [
      {
        title: "Bookings - Campus Space Booking",
      },
    ],
  }),
})

function BookingsTableContent({ status }: { status: StatusFilter }) {
  const { user: currentUser } = useAuth()
  const { data: bookings } = useSuspenseQuery(getBookingsQueryOptions(status))
  const { data: venues } = useSuspenseQuery(getVenuesQueryOptions())

  const isAdmin = Boolean(
    currentUser?.is_superuser || currentUser?.role === "admin",
  )

  const venueNames = new Map(venues.data.map((venue) => [venue.id, venue.name]))

  const tableData: BookingTableData[] = bookings.data.map((booking) => ({
    ...booking,
    venueName: venueNames.get(booking.venue_id) ?? booking.venue_id.slice(0, 8),
    canDecide: isAdmin && booking.status === "pending",
    canCancel: isAdmin || booking.user_id === currentUser?.id,
    canDelete: isAdmin,
  }))

  if (tableData.length === 0) {
    return (
      <p className="py-12 text-center text-muted-foreground">
        No bookings found.
      </p>
    )
  }

  return <DataTable columns={columns} data={tableData} />
}

function BookingsTable({ status }: { status: StatusFilter }) {
  return (
    <Suspense fallback={<PendingBookings />}>
      <BookingsTableContent status={status} />
    </Suspense>
  )
}

function Bookings() {
  const { user: currentUser } = useAuth()
  const [status, setStatus] = useState<StatusFilter>("all")

  const isAdmin = Boolean(
    currentUser?.is_superuser || currentUser?.role === "admin",
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Bookings</h1>
          <p className="text-muted-foreground">
            {isAdmin
              ? "Review and decide every booking request"
              : "Create and track your booking requests"}
          </p>
        </div>
        <AddBooking />
      </div>

      <Tabs
        value={status}
        onValueChange={(value) => setStatus(value as StatusFilter)}
      >
        <TabsList>
          {FILTERS.map((filter) => (
            <TabsTrigger key={filter} value={filter}>
              {filter.charAt(0).toUpperCase() + filter.slice(1)}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <BookingsTable status={status} />
    </div>
  )
}

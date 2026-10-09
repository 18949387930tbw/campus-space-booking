import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Check, EllipsisVertical, Trash2, X } from "lucide-react"
import { useState } from "react"

import { type BookingPublic, BookingsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

type BookingAction = "approve" | "reject" | "cancel" | "delete"

interface BookingActionsMenuProps {
  booking: BookingPublic
  canDecide: boolean
  canCancel: boolean
  canDelete: boolean
}

export const BookingActionsMenu = ({
  booking,
  canDecide,
  canCancel,
  canDelete,
}: BookingActionsMenuProps) => {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const isPending = booking.status === "pending"
  const canApprove = canDecide && isPending
  const canReject = canDecide && isPending
  const canCancelNow =
    canCancel && (booking.status === "pending" || booking.status === "approved")

  const messages: Record<BookingAction, string> = {
    approve: "Booking approved",
    reject: "Booking rejected",
    cancel: "Booking cancelled",
    delete: "Booking deleted",
  }

  const mutation = useMutation({
    mutationFn: async (action: BookingAction) => {
      if (action === "approve") {
        return BookingsService.approveBooking({
          path: { booking_id: booking.id },
        })
      }
      if (action === "reject") {
        return BookingsService.rejectBooking({
          path: { booking_id: booking.id },
        })
      }
      if (action === "cancel") {
        return BookingsService.cancelBooking({
          path: { booking_id: booking.id },
        })
      }
      return BookingsService.deleteBooking({
        path: { booking_id: booking.id },
      })
    },
    onSuccess: (_data, action) => {
      showSuccessToast(messages[action])
      setOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["bookings"] })
    },
  })

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
          <span className="sr-only">Open menu</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {canApprove && (
          <DropdownMenuItem onClick={() => mutation.mutate("approve")}>
            <Check />
            Approve
          </DropdownMenuItem>
        )}
        {canReject && (
          <DropdownMenuItem onClick={() => mutation.mutate("reject")}>
            <X />
            Reject
          </DropdownMenuItem>
        )}
        {canCancelNow && (
          <DropdownMenuItem onClick={() => mutation.mutate("cancel")}>
            <X />
            Cancel
          </DropdownMenuItem>
        )}
        {canDelete && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              variant="destructive"
              onClick={() => mutation.mutate("delete")}
            >
              <Trash2 />
              Delete
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

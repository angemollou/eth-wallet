import useAuth from "./useAuth";
import useAxiosPrivate from "./usePrivate";
import AuthContext from "../context/AuthContext";
import { useContext } from "react";

export default function useUserList() {
  const { isLoggedIn } = useAuth();
  const axiosPrivateInstance = useAxiosPrivate();
  const { setUserList } = useContext(AuthContext);

  async function getUsers(page = 1) {
    if (!isLoggedIn) {
      return;
    }

    try {
      const { data } = await axiosPrivateInstance.get("auth/users", {
        params: { page },
      });

      setUserList(data);
    } catch (error) {
      console.log("===", error.response);
    }
  }

  return getUsers;
}

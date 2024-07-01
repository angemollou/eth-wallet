import React, { useEffect, useContext, useState } from 'react'
import useAuth from '../hooks/useAuth'
import useUserList from '../hooks/useUserList';
import { AuthContext } from '../context/AuthContext';

export default function Home() {
    const { user } = useAuth();
    const { userList } = useContext(AuthContext);
    const getUsers = useUserList()
    const [page, setPage] = useState(1);


    useEffect(() => {
        getUsers()
        console.log({ user });
    }, [user, page])

    return (
        <div className='container mt-3'>
            <div className='row'>
                <div className="mb-12">
                    <h2>
                        {user?.email !== undefined ? 'List user Ethereum balance' : 'Please login first'}
                    </h2>
                </div>
                <table className="table table-sm">
                    <thead>
                        <tr>
                            <th scope="col">#</th>
                            <th scope="col">First</th>
                            <th scope="col">Last</th>
                            <th scope="col">Balance</th>
                        </tr>
                    </thead>
                    <tbody>
                        {userList.page && userList.page.map((item, i) =>
                            <tr key={i}>
                                <th scope="row">{i+1}</th>
                                <td>{item?.first_name}</td>
                                <td>{item?.last_name}</td>
                                <td>{item?.balance_eth} ETH</td>
                            </tr>
                        )}
                    </tbody>
                </table>
                <nav ariaLabel="Page navigation">
                    <ul className="pagination justify-content-center">
                        <li className="page-item">
                            <button className="page-link text-dark"
                                disabled={(page - 1) === 0}
                                onClick={() => setPage(page - 1)} ariaLabel="Previous">
                                <span ariaHidden="true">&laquo;</span>
                            </button>
                        </li>
                        {userList.pagination && userList.pagination.count
                            && <>
                                {(page - 1 > 0) && <li className="page-item">
                                    <button className="page-link text-dark" onClick={() => setPage(page - 1)}
                                    >{page - 1}</button>
                                </li>}
                                <li className="page-item">
                                    <button className="page-link text-light active">{page}</button>
                                </li>
                                {((page + 1) < userList.pagination.count) && <li className="page-item">
                                    <button className="page-link text-dark" onClick={() => setPage(page + 1)}
                                    >{page + 1}</button>
                                </li>}
                            </>
                        }
                        <li className="page-item">
                            {userList.pagination && <button className="page-link text-dark"
                                disabled={(page + 1) > userList.pagination.count}
                                onClick={() => setPage(page + 1)} ariaLabel="Next">
                                <span ariaHidden="true">&raquo;</span>
                            </button>}
                        </li>
                    </ul>
                </nav>
            </div>
        </div>
    )
}
